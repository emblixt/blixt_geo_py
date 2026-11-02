import os
import tempfile
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
from blixt_geo_py.unit_tests.plot_settings import show_plots, show_or_close
import matplotlib.pyplot as plt
import numpy as np
from openpyxl import load_workbook
import pandas as pd

from blixt_geo_py import Q_
from blixt_geo_py.core.core import Cutoffs, CutoffRule, LithoFluid, LithoFluids, LogTable
from blixt_geo_py.core.project import Project
from blixt_geo_py.analysis.calc_statistics import (IntervalStats, StatsCalculation, break_at_gaps,
                                                collect_interval_stats, isolated_samples, linear_depth_trend,
                                                to_cutoffs)

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))
project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')

log_table = {'P velocity': 'vp_dry', 'S velocity': 'vs_dry', 'Density': 'rho_dry', 'Porosity': 'phie',
             'Volume': 'vcl'}
wi_sands = ['Sand F', 'Sand E', 'Sand D']
wi_shales = ['Shale G', 'Shale C']


def make_project():
    wp = Project(name='MyProject', project_table=project_table)
    wp.load_all_wells()
    assert wp.wells is not None, 'No wells loaded from {}'.format(project_table)
    return wp, wp.wells, wp.load_all_wis()


def read_rokdoc_lines(file_name):
    """
    Returns the data lines of a RokDoc Sums and Averages file as a list of {column name: value}
    """
    wb = load_workbook(file_name)
    rows = [_r for _r in wb.active.iter_rows(values_only=True)]
    wb.close()
    # The data lines follow the line with the column names
    header_index = [_r[0] for _r in rows].index('Name')
    columns = rows[header_index]
    return [dict(zip(columns, _r)) for _r in rows[header_index + 1:]]


class TestCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.wp, cls.wells, cls.wis = make_project()

    def test_to_cutoffs(self):
        from_dict = to_cutoffs({'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]})
        from_str = to_cutoffs('Volume<0.5[], Porosity>0.1[]')
        for _c in [from_dict, from_str]:
            self.assertEqual(_c.cutoff_params, ['Volume', 'Porosity'])
            self.assertEqual(_c.get_dict(), {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]})
        self.assertEqual(len(to_cutoffs(None)), 0)

    def test_break_at_gaps(self):
        # Samples every 0.1 m, with the ones between 0.3 and 1.0 m removed by the cutoffs
        depth = np.array([0.0, 0.1, 0.2, 0.3, 1.0, 1.1, 1.2])
        values = np.arange(len(depth))
        new_values, new_depth = break_at_gaps(values, depth)
        self.assertEqual(len(new_depth), len(depth) + 1)
        self.assertTrue(np.isnan(new_depth[4]) and np.isnan(new_values[4]))
        np.testing.assert_array_equal(new_depth[~np.isnan(new_depth)], depth)
        np.testing.assert_array_equal(new_values[~np.isnan(new_values)], values)
        # Without gaps nothing changes
        new_values, new_depth = break_at_gaps(values[:4], depth[:4])
        np.testing.assert_array_equal(new_depth, depth[:4])

    def test_isolated_samples(self):
        # A single sample between two gaps, one at the start, and one next to a NaN in the log
        depth = np.array([0.0, np.nan, 0.5, 0.6, np.nan, 1.0, np.nan, 1.5, 1.6, 1.7])
        values = np.array([1., np.nan, 2., 3., np.nan, 4., np.nan, 5., np.nan, 6.])
        np.testing.assert_array_equal(
            isolated_samples(values, depth),
            [True, False, False, False, False, True, False, True, False, True])

    def test_collect_interval_stats(self):
        cutoffs = Cutoffs([CutoffRule('Volume', '<', Q_(0.5, '')), CutoffRule('Porosity', '>', Q_(0.1, ''))])
        n_rules = len(cutoffs)
        stats = collect_interval_stats(self.wells, self.wis, 'Sand F', LogTable(dict(log_table)), cutoffs)
        self.assertIsInstance(stats, IntervalStats)
        # The interval rule must not be added to the cutoffs given by the user
        self.assertEqual(len(cutoffs), n_rules)
        self.assertIn('WELL_F', stats.well_names)

        interval = self.wis.get_interval('Sand F', 'WELL_F')
        data = stats.per_well['WELL_F']
        depth_from_top = stats.depth_from_top['WELL_F'].to('m').magnitude
        self.assertGreater(len(depth_from_top), 0)
        # All data lies inside the interval, and passes the cutoffs
        self.assertTrue(np.all(depth_from_top >= 0.))
        self.assertTrue(np.all(depth_from_top <= interval.thickness.to('m').magnitude))
        self.assertTrue(np.all(data['vcl'].magnitude < 0.5))
        self.assertTrue(np.all(data['phie'].magnitude > 0.1))
        for _log in log_table.values():
            self.assertEqual(len(data[_log]), len(depth_from_top))

        if show_plots:
            # Selected data versus depth from the top of the interval
            fig, axes = plt.subplots(ncols=len(log_table), figsize=(2 * len(log_table), 4), sharey=True)
            for ax, _log in zip(axes, log_table.values()):
                ax.plot(data[_log].magnitude, depth_from_top, '.', ms=2)
                ax.set_xlabel('{} [{}]'.format(_log, data[_log].units))
            axes[0].set_ylabel('Depth from top of Sand F [m]')
            axes[0].invert_yaxis()
            fig.suptitle('WELL_F, Sand F: {}'.format(cutoffs))
            fig.tight_layout()
        show_or_close()

    def test_missing_interval(self):
        # WELL_F has no 'Abenaki' interval, so no data should be collected (and not the whole well)
        if self.wis.get_interval('Abenaki', 'WELL_F') is not None:
            self.skipTest('WELL_F has the Abenaki interval')
        stats = collect_interval_stats(self.wells, self.wis, 'Abenaki', LogTable(dict(log_table)), Cutoffs([]))
        self.assertNotIn('WELL_F', stats.well_names)

    def test_summary(self):
        stats = StatsCalculation(self.wells, self.wis, wi_sands, log_table, {'Volume': ['<', 0.5]}, 'sands')
        results = stats.run()
        self.assertEqual(list(results.keys()), wi_sands)
        summary = stats.summary(results)
        all_rows = summary[summary['well'] == 'All']
        self.assertEqual(set(all_rows['log']), set(log_table.values()))
        # Statistics of 'All' must equal those of the combined data
        combined = results['Sand F'].combined()
        row = all_rows[(all_rows['interval'] == 'Sand F') & (all_rows['log'] == 'vp_dry')].iloc[0]
        self.assertAlmostEqual(row['mean'], np.nanmean(combined['vp_dry'].magnitude))

    def test_input_checks(self):
        with self.assertRaises(ValueError):
            StatsCalculation(self.wells, self.wis, wi_sands, log_table, [{'Volume': ['<', 0.5]}])
        with self.assertRaises(TypeError):
            StatsCalculation(['WELL_F'], self.wis, wi_sands, log_table)
        # log_table and cutoffs in the wrong order must give an error that says so
        for _cutoffs in [{'Volume': ['<', 0.5]}, 'Volume<0.5[]', None]:
            with self.subTest(cutoffs=_cutoffs):
                with self.assertRaisesRegex(TypeError, 'log_table comes before cutoffs'):
                    StatsCalculation(self.wells, self.wis, wi_sands, _cutoffs, log_table)

    def test_no_cutoffs(self):
        """
        Without cutoffs all samples of the interval are used, regardless of lithology
        """
        stats = StatsCalculation(self.wells, self.wis, 'Sand F', log_table)
        results = stats.run()
        self.assertEqual(0, len(results['Sand F'].cutoffs))
        with_cutoffs = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, {'Volume': ['<', 0.5]}).run()

        interval = self.wis.get_interval('Sand F', 'WELL_F')
        well = next(_w for _w in (self.wells.values() if isinstance(self.wells, dict) else self.wells)
                    if _w.name == 'WELL_F')
        md = well.dict()['md'].to('m').magnitude
        # Including the samples at the top and the base
        n_samples = np.sum((md >= interval.top.to('m').magnitude) & (md <= interval.base.to('m').magnitude))
        self.assertEqual(n_samples, len(results['Sand F'].per_well['WELL_F']['vp_dry']))
        self.assertLess(len(with_cutoffs['Sand F'].per_well['WELL_F']['vp_dry']), n_samples)

        # A repeated interval can have cutoffs in only one of them
        results = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand F'], log_table, [None, {'Volume': ['<', 0.5]}],
                                   ['all', 'sand']).run()
        self.assertEqual(n_samples, len(results['Sand F, all'].per_well['WELL_F']['vp_dry']))
        self.assertLess(len(results['Sand F, sand'].per_well['WELL_F']['vp_dry']), n_samples)

        # All the outputs work without cutoffs
        results = stats.run()
        self.assertEqual(4 * len(log_table), len(stats.summary(results)))
        stats.plot_logs_vs_depth(results, file_name=None)
        stats.plot_averages(results)
        stats.plot_logs_vs_burial_depth(results, file_name=None)
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output(results, file_name)
            self.assertEqual(4, len(read_rokdoc_lines(file_name)))
        show_or_close()

    def test_calc_stat(self):
        cutoffs_sands = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}
        cutoffs_shales = {'Volume': ['>', 0.5], 'Porosity': ['<', 0.1]}
        stats = StatsCalculation(
            self.wells, self.wis, wi_sands + wi_shales,
            log_table,
            [cutoffs_sands] * len(wi_sands) + [cutoffs_shales] * len(wi_shales),
            ['sands'] * len(wi_sands) + ['shales'] * len(wi_shales),
            )
        results = stats.run()
        stats.plot_logs_vs_depth(results, file_name=None)
        figs = stats.plot_averages(results)
        self.assertEqual(list(figs.keys()), list(log_table.keys()))
        print(stats.summary(results).to_string())
        show_or_close()

    def test_write_rokdoc_sums_and_averages(self):
        """
        Write the averages of synthetic data to a RokDoc Sums and Averages file, and read them back
        """
        from blixt_geo_py.analysis.calc_statistics import write_rokdoc_sums_and_averages

        _log_table = LogTable(log_table)
        rng = np.random.default_rng(0)
        # Arrays without units, with the log names as keys, as StatsCalculation.save_rokdoc_output() passes them
        results = {'vp_dry': rng.normal(3000., 100., 50), 'vs_dry': rng.normal(1500., 50., 50),
                   'rho_dry': rng.normal(2.3, 0.05, 50), 'phie': rng.normal(0.2, 0.02, 50),
                   'vcl': rng.normal(0.1, 0.01, 50)}

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            # The first call creates the file, the second appends a line to it
            write_rokdoc_sums_and_averages(file_name, results, 'Sand F', _log_table, 'vcl<0.5', '_test')
            write_rokdoc_sums_and_averages(file_name, results, 'Sand F', _log_table, 'vcl<0.5', '_test',
                                           well_name='WELL_A')

            lines = read_rokdoc_lines(file_name)

        self.assertEqual(2, len(lines))

        # The line without a well name holds the averages of all wells
        self.assertEqual(('Sand F_test', 'NONE'), (lines[0]['Name'], lines[0]['Well']))
        self.assertEqual(('WELL_A Sand F_test', 'WELL_A'), (lines[1]['Name'], lines[1]['Well']))
        for line in lines:
            self.assertAlmostEqual(np.mean(results['vp_dry']), line['VpMean'])
            self.assertAlmostEqual(np.median(results['vs_dry']), line['VsMedian'])
            self.assertAlmostEqual(np.std(results['rho_dry']), line['RhoStdDev'])
            self.assertAlmostEqual(np.mean(results['phie']), line['PorosityMean'])

    def test_repeated_interval(self):
        """
        One interval with different cutoffs for sand and shale must give two results, equal to running them one by one
        """
        sand, shale = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}, {'Volume': ['>', 0.5]}
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand F', 'Sand E'], log_table, [sand, shale, sand],
                                 ['sand', 'shale', 'sand'])
        results = stats.run()
        # Only the repeated interval has the suffix in its key
        self.assertEqual(['Sand F, sand', 'Sand F, shale', 'Sand E'], list(results.keys()))

        for _key, _cutoffs, _suffix in [('Sand F, sand', sand, 'sand'), ('Sand F, shale', shale, 'shale')]:
            alone = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, _cutoffs, _suffix).run()['Sand F']
            self.assertEqual(_suffix, results[_key].suffix)
            for _well in alone.well_names:
                np.testing.assert_array_equal(alone.per_well[_well]['vp_dry'].magnitude,
                                              results[_key].per_well[_well]['vp_dry'].magnitude)

        # The two must differ, or this test could not detect one overwriting the other
        self.assertNotEqual(len(results['Sand F, sand'].per_well['WELL_B']['vp_dry']),
                            len(results['Sand F, shale'].per_well['WELL_B']['vp_dry']))

        # The summary tells them apart
        summary = stats.summary(results)
        rows = summary[(summary['interval'] == 'Sand F') & (summary['well'] == 'WELL_B') & (summary['log'] == 'vp_dry')]
        self.assertEqual(['sand', 'shale'], list(rows['suffix']))
        self.assertEqual([len(results['Sand F, sand'].per_well['WELL_B']['vp_dry']),
                          len(results['Sand F, shale'].per_well['WELL_B']['vp_dry'])], list(rows['n']))

        # So does the RokDoc output
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output(results, file_name)
            names = [_l['Name'] for _l in read_rokdoc_lines(file_name)]
        self.assertEqual(len(names), len(set(names)))
        for _name in ['Sand F_sand', 'Sand F_shale', 'WELL_B Sand F_sand', 'WELL_B Sand F_shale']:
            self.assertIn(_name, names)

        # All plots show one row, or one tick, per result
        self.assertEqual(3 * len(log_table), len(stats.plot_logs_vs_burial_depth(results, file_name=None)[0].axes))
        self.assertEqual(3 * len(log_table), len(stats.plot_logs_vs_depth(results, file_name=None).axes))
        ax = stats.plot_averages(results)['P velocity'].axes[0]
        self.assertEqual(['Sand F, sand', 'Sand F, shale', 'Sand E, sand'], [_t.get_text() for _t in ax.get_yticklabels()])
        show_or_close()

    def test_repeated_interval_needs_different_suffixes(self):
        sand, shale = {'Volume': ['<', 0.5]}, {'Volume': ['>', 0.5]}
        for _suffix in ['', 'same', ['same', 'same']]:
            with self.subTest(suffix=_suffix):
                with self.assertRaisesRegex(ValueError, 'Sand F'):
                    StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand F'], log_table, [sand, shale], _suffix)
        # A single suffix is fine as long as the intervals differ, and they keep their plain names
        results = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, sand, 'same').run()
        self.assertEqual(['Sand F', 'Sand E'], list(results.keys()))

    def test_linear_depth_trend(self):
        rng = np.random.default_rng(0)
        tvd = np.linspace(1000., 3000., 500)
        values = 1500. + 0.8 * tvd + rng.normal(0., 50., len(tvd))
        # NaN in either array must be ignored
        values[10] = np.nan
        tvd_with_nan = tvd.copy()
        tvd_with_nan[20] = np.nan
        trend = linear_depth_trend(values, tvd_with_nan)
        self.assertEqual(498, trend['n'])
        self.assertAlmostEqual(0.8, trend['slope'], delta=0.02)
        self.assertAlmostEqual(1500., trend['intercept'], delta=50.)
        self.assertGreater(trend['r2'], 0.95)
        self.assertAlmostEqual(50., trend['std_detrended'], delta=5.)
        self.assertGreater(trend['std'], 400.)

        # No trend
        trend = linear_depth_trend(rng.normal(0., 50., len(tvd)), tvd)
        self.assertLess(trend['r2'], 0.05)
        self.assertAlmostEqual(trend['std'], trend['std_detrended'], delta=1.)
        self.assertEqual(0., linear_depth_trend(np.ones(10), np.arange(10.))['r2'])

        # A trend can't be calculated
        self.assertIsNone(linear_depth_trend(np.array([1., 2.]), np.array([1., 2.])))
        self.assertIsNone(linear_depth_trend(np.array([1., 2., 3.]), np.array([5., 5., 5.])))
        self.assertIsNone(linear_depth_trend(np.array([np.nan] * 4), np.arange(4.)))

    def test_samples_with_burial_depth(self):
        stats = IntervalStats('Sand', LogTable({'P velocity': 'vp'}), Cutoffs([]))
        self.assertEqual((None, None), stats.samples_with_burial_depth('vp'))
        stats.per_well = {'A': {'vp': Q_(np.array([3000., 3100.]), 'm/s')},
                          'B': {'vp': Q_(np.array([3.2]), 'km/s')},
                          'No burial depth': {'vp': Q_(np.array([9999.]), 'm/s')},
                          'No samples': {'vp': Q_(np.array([]), 'm/s')}}
        stats.burial_depth = {'A': Q_(np.array([1000., 1001.]), 'm'), 'B': Q_(np.array([2.]), 'km'),
                              'No samples': Q_(np.array([]), 'm')}
        values, depth = stats.samples_with_burial_depth('vp')
        np.testing.assert_allclose([3000., 3100., 3200.], values.to('m/s').magnitude)
        np.testing.assert_allclose([1000., 1001., 2000.], depth)

    def test_plot_logs_vs_burial_depth(self):
        """
        WELL_A has no TVD log, and the kelly bushing and water depth of WELL_B are blank in the project table, so
        here they are set in a separately loaded copy of the wells
        """
        _, wells, wis = make_project()
        wells_by_name = {_w.name: _w for _w in (wells.values() if isinstance(wells, dict) else wells)}
        wells_by_name['WELL_B'].header['kb'] = Q_(30., 'm')
        wells_by_name['WELL_B'].header['water_depth'] = Q_(300., 'm')

        stats = StatsCalculation(wells, wis, ['Sand F', 'Sand D'], log_table,
                                 {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]})
        results = stats.run()
        sand_f = results['Sand F']
        self.assertEqual({'WELL_B', 'WELL_F'}, set(sand_f.burial_depth.keys()))
        self.assertEqual(len(sand_f.per_well['WELL_B']['vp_dry']), len(sand_f.burial_depth['WELL_B']))

        # The burial depth is the TVD below the kelly bushing, minus the kelly bushing and the water depth
        for _name, _kb_and_water_depth in [('WELL_B', 330.), ('WELL_F', 125.)]:
            _data = wells_by_name[_name].dict()
            np.testing.assert_allclose(_data['tvd'].to('m').magnitude - _kb_and_water_depth,
                                       _data['tvd_ml'].to('m').magnitude, atol=1e-6)

        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            figs = stats.plot_logs_vs_burial_depth(results, file_name='logs_vs_burial_depth.png')
            self.assertTrue(os.path.isfile(os.path.join(tmp_dir, 'logs_vs_burial_depth.png')))

        self.assertEqual(1, len(figs))
        fig = figs[0]
        self.assertEqual(2 * len(log_table), len(fig.axes))
        self.assertIn('WELL_A', fig._suptitle.get_text())
        self.assertNotIn('WELL_B', fig._suptitle.get_text())
        ax = fig.axes[0]
        self.assertIn('Burial depth', ax.get_ylabel())
        # Depth increases downwards
        self.assertGreater(ax.get_ylim()[0], ax.get_ylim()[1])
        # The trend line is calculated from the wells with burial depth, and is not drawn outside of their depth range
        values, depth = sand_f.samples_with_burial_depth('vp_dry')
        trend = linear_depth_trend(values.magnitude, depth)
        x, y = ax.get_lines()[-1].get_data()
        self.assertAlmostEqual(trend['slope'], (x[1] - x[0]) / (y[1] - y[0]))
        self.assertAlmostEqual(np.nanmax(depth), y[1])
        self.assertIn('2 wells', ax.get_title(loc='left'))
        self.assertIn('R2 = {:.2f}'.format(trend['r2']), ax.get_title(loc='left'))
        # WELL_B has no samples in Sand D, so that trend is only based on one well
        self.assertIn('1 well,', fig.axes[len(log_table)].get_title(loc='left'))
        show_or_close()

    def test_plot_logs_vs_burial_depth_many_intervals(self):
        """
        With more than max_intervals intervals, the plot is split into several figures, keeping the order
        """
        names = wi_sands + wi_shales + ['Sand F']
        suffixes = ['first', '', '', '', '', 'last']
        stats = StatsCalculation(self.wells, self.wis, names, log_table, {'Volume': ['<', 0.5]}, suffixes)
        results = stats.run()
        n_logs = len(log_table)

        def y_labels(_fig):
            return [_ax.get_ylabel() for _ax in _fig.axes[::n_logs]]

        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            # Six intervals: five in the first figure, and one in the second
            figs = stats.plot_logs_vs_burial_depth(results)
            self.assertEqual(['logs_vs_burial_depth_1.png', 'logs_vs_burial_depth_2.png'], sorted(os.listdir(tmp_dir)))
            self.assertEqual([5 * n_logs, n_logs], [len(_f.axes) for _f in figs])
            self.assertIn('Sand F, first', y_labels(figs[0])[0])
            self.assertIn('Sand F, last', y_labels(figs[1])[0])
            show_or_close()

        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            # Exactly five intervals fit in one figure, whose file name has no number
            five = dict(list(results.items())[:5])
            self.assertEqual(1, len(stats.plot_logs_vs_burial_depth(five)))
            self.assertEqual(['logs_vs_burial_depth.png'], os.listdir(tmp_dir))
            # No empty figure when the intervals fill up the last one
            self.assertEqual([2 * n_logs, 2 * n_logs, n_logs],
                             [len(_f.axes) for _f in stats.plot_logs_vs_burial_depth(five, None, max_intervals=2)])
            self.assertEqual(2, len(stats.plot_logs_vs_burial_depth(dict(list(results.items())[:4]), None,
                                                                    max_intervals=2)))
            show_or_close()

    def test_lacking_burial_depth_per_figure(self):
        """
        The title of each figure only lists the wells that are lacking in that figure
        """
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, {'Volume': ['<', 0.5]})
        results = stats.run()
        results['Sand F'].per_well.pop('WELL_B')
        results['Sand E'].per_well.pop('WELL_A')
        first, second = stats.plot_logs_vs_burial_depth(results, file_name=None, max_intervals=1)
        self.assertIn('WELL_A', first._suptitle.get_text())
        self.assertNotIn('WELL_B', first._suptitle.get_text())
        self.assertIn('WELL_B', second._suptitle.get_text())
        self.assertNotIn('WELL_A', second._suptitle.get_text())
        show_or_close()

    def test_burial_depth_lacking_kb_and_water_depth(self):
        """
        With the kelly bushing and water depth of WELL_B blank in the project table, its burial depth is all NaN.
        It must be reported as lacking, as WELL_A without a TVD log, instead of disappearing from the plot unnoticed
        """
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand D'], log_table,
                                 {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]})
        results = stats.run()
        self.assertEqual({'WELL_F'}, set(results['Sand F'].burial_depth.keys()))
        fig = stats.plot_logs_vs_burial_depth(results, file_name=None)[0]
        self.assertIn('WELL_A', fig._suptitle.get_text())
        self.assertIn('WELL_B', fig._suptitle.get_text())
        self.assertNotIn('WELL_F', fig._suptitle.get_text())
        self.assertIn('1 well,', fig.axes[0].get_title(loc='left'))
        show_or_close()

    def test_plot_logs_vs_burial_depth_without_any(self):
        """
        Without the burial depth in any well the plot is empty, but must not fail
        """
        stats = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, {'Volume': ['<', 0.5]})
        results = stats.run()
        results['Sand F'].burial_depth = {}
        fig = stats.plot_logs_vs_burial_depth(results, file_name=None)[0]
        self.assertEqual(0, len(fig.axes[0].collections))
        for _well in ['WELL_A', 'WELL_B', 'WELL_F']:
            self.assertIn(_well, fig._suptitle.get_text())
        show_or_close()

    def test_save_rokdoc_output(self):
        """
        Write the averages of the test wells to a RokDoc Sums and Averages file, and read them back.
        The cutoffs leave no samples of Sand D in WELL_B
        """
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand D'], log_table,
                                 {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]})
        results = stats.run()

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output(results, file_name)
            lines = {_l['Name']: _l for _l in read_rokdoc_lines(file_name)}
            # The file is read back as litho fluids, where a lack of samples must not give a velocity of -999.25
            lf_data = LithoFluid()
            lf_data.from_excel(file_name, 'WELL_A Sand F')
            lf_empty = LithoFluid()
            lf_empty.from_excel(file_name, 'WELL_B Sand D')
            lfs = LithoFluids()
            lfs.from_excel(file_name)

        self.assertEqual(len(lines), len(lfs.litho_fluids))
        self.assertAlmostEqual(lines['WELL_A Sand F']['VpMean'], lf_data.vp.magnitude)
        for _q in [lf_empty.vp, lf_empty.vs, lf_empty.rho, lf_empty.vp_std_dev, lf_empty.vp_vs_cc]:
            self.assertTrue(np.isnan(_q.magnitude))

        # One line for all wells together, and one for each well, of each interval
        self.assertEqual(sum(1 + len(_r.per_well) for _r in results.values()), len(lines))
        combined = results['Sand F'].combined()
        self.assertAlmostEqual(np.nanmean(combined['vp_dry'].magnitude), lines['Sand F']['VpMean'])
        self.assertEqual('NONE', lines['Sand F']['Well'])
        well_a = results['Sand F'].per_well['WELL_A']
        self.assertAlmostEqual(np.nanmean(well_a['vp_dry'].magnitude), lines['WELL_A Sand F']['VpMean'])

        # An interval without samples holds the null value, and no empty cells
        empty = lines['WELL_B Sand D']
        for _key in ['VpMean', 'VsMedian', 'RhoStdDev', 'PorosityMean', 'ShaleVolumeMean', 'VpVsCorrCoef']:
            self.assertEqual(-999.25, empty[_key])

    def test_save_rokdoc_output_lacking_logs(self):
        """
        An interval lacking some of the logs RokDoc needs is skipped, so no file is created here
        """
        _log_table = {_k: _v for _k, _v in log_table.items() if _k != 'Density'}
        stats = StatsCalculation(self.wells, self.wis, 'Sand F', _log_table, {'Volume': ['<', 0.5]})
        results = stats.run()

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output(results, file_name)
            self.assertFalse(os.path.isfile(file_name))

    def test_save_summary(self):
        """
        Write the statistics to an excel file and read them back. Writing twice must not add any lines
        """
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand D'], log_table,
                                 {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]})
        results = stats.run()
        summary = stats.summary(results)

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'summary.xlsx')
            stats.save_summary(results, file_name)
            stats.save_summary(results, file_name)
            saved = pd.read_excel(file_name)

        self.assertEqual(list(summary.columns), list(saved.columns))
        self.assertEqual(len(summary), len(saved))
        np.testing.assert_allclose(summary['mean'], saved['mean'])
        # An interval without samples has no statistics
        empty = saved[(saved['interval'] == 'Sand D') & (saved['well'] == 'WELL_B')]
        self.assertTrue((empty['n'] == 0).all())
        self.assertTrue(empty['mean'].isna().all())


if __name__ == '__main__':
    unittest.main()
