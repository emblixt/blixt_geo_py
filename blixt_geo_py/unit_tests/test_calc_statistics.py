import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

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
                                                collect_interval_stats, fit_gardner, isolated_samples, linear_depth_trend,
                                                pair_correlation, read_gardner, to_cutoffs)

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))
project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
results_folder = os.path.join(project_dir, 'blixt_geo_py\\results_folder')

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


def open_for_inspection(file_name, inspection_name):
    """
    If show_plots is True (see plot_settings.py), copies a file written to a temporary folder by a test to the results
    folder, under the name inspection_name, and opens it in the default program for that file type (e.g. Excel)
    """
    if not show_plots:
        return
    target = os.path.join(results_folder, inspection_name)
    try:
        shutil.copyfile(file_name, target)
    except PermissionError:
        print('Could not update {}. Close it in Excel and run the test again'.format(target))
        return
    print('File for inspection: {}'.format(target))
    os.startfile(target)


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

    def test_multi_log_table(self):
        # Asks once, not once per interval, and gives the same results as a table with the selected logs
        multi_log_table = dict(log_table, **{'Volume': ['vsh_not_used', 'vcl']})
        names, cutoffs = ['Sand F', 'Sand E'], 'Volume<0.5[], Porosity>0.1[]'
        with patch('builtins.input', side_effect=['1']) as mock_input:
            stats = StatsCalculation(self.wells, self.wis, names, multi_log_table, cutoffs)
            results = stats.run()
        self.assertEqual(1, mock_input.call_count)
        expected = StatsCalculation(self.wells, self.wis, names, log_table, cutoffs).run()
        pd.testing.assert_frame_equal(stats.summary(expected), stats.summary(results))

        # The same LogTable given to a function on its own
        with patch('builtins.input', side_effect=['1']) as mock_input:
            one_interval = collect_interval_stats(self.wells, self.wis, 'Sand F', LogTable(multi_log_table),
                                                  to_cutoffs(cutoffs))
        self.assertEqual(1, mock_input.call_count)
        self.assertEqual('vcl', one_interval.log_table['Volume'])

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

    def test_fit_gardner(self):
        rng = np.random.default_rng(0)
        vp = rng.uniform(2000., 5000., 1000)

        # Without noise the coefficients are recovered exactly
        fit = fit_gardner(vp, 0.31 * vp ** 0.25)
        self.assertAlmostEqual(0.31, fit['a'])
        self.assertAlmostEqual(0.25, fit['b'])
        self.assertAlmostEqual(1., fit['r2'])
        self.assertEqual(len(vp), fit['n'])

        # With noise they are close, for another set of coefficients
        fit = fit_gardner(vp, 0.5 * vp ** 0.2 * np.exp(rng.normal(0., 0.01, len(vp))))
        self.assertAlmostEqual(0.2, fit['b'], delta=0.005)
        self.assertAlmostEqual(0.5, fit['a'], delta=0.05)
        self.assertGreater(fit['r2'], 0.5)
        self.assertLess(fit['r2'], 1.)

        # Samples without a defined logarithm are ignored
        bad_vp, bad_rho = vp.copy(), 0.31 * vp ** 0.25
        bad_vp[:4] = [np.nan, 0., -999.25, np.inf]
        bad_rho[4:7] = [np.nan, 0., -999.25]
        fit = fit_gardner(bad_vp, bad_rho)
        self.assertEqual(len(vp) - 7, fit['n'])
        self.assertAlmostEqual(0.25, fit['b'])

        # A constant density is an exponent of zero
        fit = fit_gardner(vp, np.full(len(vp), 2.5))
        self.assertAlmostEqual(0., fit['b'])
        self.assertAlmostEqual(2.5, fit['a'])
        self.assertEqual(0., fit['r2'])

        # A fit can't be calculated
        self.assertIsNone(fit_gardner(np.array([3000., 3100.]), np.array([2.3, 2.4])))
        self.assertIsNone(fit_gardner(np.full(5, 3000.), np.linspace(2.2, 2.6, 5)))
        self.assertIsNone(fit_gardner(np.array([np.nan] * 5), np.linspace(2.2, 2.6, 5)))

    def test_gardner_units_and_wells(self):
        """
        The coefficients are for m/s and g/cm3 whatever the units of the logs, and 'All' only uses wells with both logs
        """
        vp = np.linspace(2000., 5000., 50)
        rho = 0.31 * vp ** 0.25
        stats = IntervalStats('Sand', LogTable({'P velocity': 'vp', 'Density': 'rho'}), Cutoffs([]), 'sand')
        stats.per_well = {'In km/s and kg/m3': {'vp': Q_(vp / 1000., 'km/s'), 'rho': Q_(rho * 1000., 'kg/m**3')},
                          'No density': {'vp': Q_(np.array([1000.] * 7), 'm/s')},
                          'No samples': {'vp': Q_(np.array([]), 'm/s'), 'rho': Q_(np.array([]), 'g/cm**3')}}
        table = stats.gardner().set_index('well')
        self.assertEqual({'In km/s and kg/m3', 'No samples', 'All'}, set(table.index))
        self.assertAlmostEqual(0.31, table.loc['In km/s and kg/m3', 'a'])
        self.assertAlmostEqual(0.25, table.loc['In km/s and kg/m3', 'b'])
        self.assertEqual(50, table.loc['All', 'n'])
        self.assertAlmostEqual(0.31, table.loc['All', 'a'])
        self.assertEqual(0, table.loc['No samples', 'n'])
        self.assertTrue(np.isnan(table.loc['No samples', 'a']))
        self.assertEqual('sand', table.loc['All', 'suffix'])
        self.assertEqual('m/s', table.loc['All', 'vp units'])

        # A log table without the needed logs gives an empty table with the same columns
        lacking = IntervalStats('Sand', LogTable({'P velocity': 'vp'}), Cutoffs([]))
        lacking.per_well = {'A': {'vp': Q_(vp, 'm/s')}}
        self.assertEqual(0, len(lacking.gardner()))
        self.assertEqual(sorted(table.reset_index().columns), sorted(lacking.gardner().columns))

    def test_gardner_per_interval_and_cutoff(self):
        sand, shale = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}, {'Volume': ['>', 0.5]}
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand F', 'Sand D'], log_table, [sand, shale, sand],
                                 ['sand', 'shale', 'sand'])
        results = stats.run()
        table = stats.gardner(results)
        # One row per well, and for all wells, of each of the three
        self.assertEqual(3 * 4, len(table))
        rows = table[(table['interval'] == 'Sand F') & (table['well'] == 'WELL_A')]
        self.assertEqual(['sand', 'shale'], list(rows['suffix']))
        self.assertNotEqual(rows['a'].iloc[0], rows['a'].iloc[1])

        # Matches a fit directly on the logs
        data = results['Sand F, sand'].per_well['WELL_A']
        fit = fit_gardner(data['vp_dry'].to('m/s').magnitude, data['rho_dry'].to('g/cm**3').magnitude)
        self.assertAlmostEqual(fit['a'], rows['a'].iloc[0])
        self.assertAlmostEqual(fit['b'], rows['b'].iloc[0])
        self.assertEqual(fit['n'], rows['n'].iloc[0])

        # WELL_B has no samples of Sand D with these cutoffs
        no_samples = table[(table['interval'] == 'Sand D') & (table['well'] == 'WELL_B')].iloc[0]
        self.assertEqual(0, no_samples['n'])
        self.assertTrue(np.isnan(no_samples['a']))

        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            fig = stats.plot_gardner(results)
            self.assertTrue(os.path.isfile(os.path.join(tmp_dir, 'gardner.png')))
        visible = [_ax for _ax in fig.axes if _ax.get_visible()]
        self.assertEqual(3, len(visible))
        self.assertIn('Sand F, sand', visible[0].get_title(loc='left'))
        all_row = table[(table['suffix'] == 'sand') & (table['interval'] == 'Sand F') & (table['well'] == 'All')].iloc[0]
        self.assertIn('a = {:.3f}, b = {:.3f}'.format(all_row['a'], all_row['b']), visible[0].get_title(loc='left'))
        self.assertEqual('Vp [m/s]', visible[0].get_xlabel())
        show_or_close()

    def test_save_and_read_gardner(self):
        sand, shale = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}, {'Volume': ['>', 0.5]}
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand F', 'Sand D', 'Shale G'], log_table,
                                 [sand, shale, sand, None], ['sand', 'shale', 'sand', ''])
        results = stats.run()
        table = stats.gardner(results)

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'gardner.xlsx')
            # Saving twice overwrites the file
            stats.save_gardner(results, file_name)
            stats.save_gardner(results, file_name)
            self.assertEqual(len(table), len(pd.read_excel(file_name)))

            # Every coefficient that can be calculated is read back
            for _, _row in table.dropna(subset=['a']).iterrows():
                a, b = read_gardner(file_name, _row['interval'], _row['suffix'], _row['well'])
                self.assertAlmostEqual(_row['a'], a)
                self.assertAlmostEqual(_row['b'], b)
                self.assertIsInstance(a, float)

            # The defaults are all wells, and no suffix
            row = table[(table['interval'] == 'Shale G') & (table['well'] == 'All')].iloc[0]
            self.assertEqual('', row['suffix'])
            self.assertAlmostEqual(row['a'], read_gardner(file_name, 'Shale G')[0])

            # The suffix tells a repeated interval apart
            self.assertNotEqual(read_gardner(file_name, 'Sand F', 'sand'), read_gardner(file_name, 'Sand F', 'shale'))

            # No match, with the content of the file in the error
            for _args in [('Abenaki',), ('Sand F',), ('Sand F', 'sand', 'NO_SUCH_WELL')]:
                with self.subTest(args=_args):
                    with self.assertRaisesRegex(ValueError, 'Found 0 lines.*Sand F, suffix "shale"'):
                        read_gardner(file_name, *_args)

            # WELL_B has no samples of Sand D with these cutoffs, which must not give NaN densities later
            with self.assertRaisesRegex(ValueError, r'too few samples \(0\)'):
                read_gardner(file_name, 'Sand D', 'sand', 'WELL_B')

    def test_plot_gardner_panels(self):
        """
        A panel that is lowest in its column shows the x axis, also when the last row isn't full
        """
        stats = StatsCalculation(self.wells, self.wis, wi_sands + wi_shales, log_table, {'Volume': ['<', 0.5]})
        results = stats.run()
        fig = stats.plot_gardner(results, file_name=None, n_columns=3)
        self.assertEqual(6, len(fig.axes))
        self.assertFalse(fig.axes[5].get_visible())
        for _i in [2, 3, 4]:
            self.assertEqual('Vp [m/s]', fig.axes[_i].get_xlabel())
        # A single interval gives a single panel
        one = stats.plot_gardner({'Sand F': results['Sand F']}, file_name=None)
        self.assertEqual(1, len(one.axes))
        show_or_close()

    def test_well_style_comes_from_the_project_table(self):
        from blixt_geo_py.plotting import crossplot as xp
        stats = StatsCalculation(self.wells, self.wis, ['Sand F'], log_table, {'Volume': ['<', 0.5]})
        self.assertEqual(('#1f77b4', 'o'), stats.well_style('WELL_A', 0))
        self.assertEqual(('#ff7f0e', 's'), stats.well_style('WELL_B', 1))
        # The default cycles are used for a well that isn't known
        self.assertEqual((xp.cnames[1], xp.msymbols[1]), stats.well_style('NO_SUCH_WELL', 1))

    def test_plot_gardner_uses_the_well_styles(self):
        stats = StatsCalculation(self.wells, self.wis, ['Sand F'], log_table, {'Volume': ['<', 0.5]})
        results = stats.run()
        fig = stats.plot_gardner(results, file_name=None)
        ax = fig.axes[0]

        # One mean with error bars per well, in the style of that well
        samples = results['Sand F'].vp_and_rho()
        wells = [_w for _w in samples if _w != 'All']
        self.assertEqual(len(wells), len(ax.containers))
        all_wells = [_w.name for _w in stats.wells]
        for well_name, container in zip(wells, ax.containers):
            color, marker = stats.well_style(well_name, all_wells.index(well_name))
            line = container.lines[0]
            self.assertEqual(marker, line.get_marker())
            self.assertEqual(color, line.get_color())
            self.assertTrue(container.has_xerr and container.has_yerr)
            vp, rho = samples[well_name]
            self.assertAlmostEqual(np.nanmean(vp), line.get_xdata()[0])
            self.assertAlmostEqual(np.nanmean(rho), line.get_ydata()[0])

        # The legend has the wells and all wells together
        labels = [_t.get_text() for _t in fig.legends[0].get_texts()]
        for _label in wells + ['All wells']:
            self.assertIn(_label, labels)
        show_or_close()

    def test_ai_and_vpvs(self):
        stats = StatsCalculation(self.wells, self.wis, ['Sand F'], log_table, {'Volume': ['<', 0.5]})
        result = stats.run()['Sand F']
        samples = result.ai_and_vpvs()
        self.assertEqual(result.well_names + ['All'], list(samples.keys()))

        data = result.per_well['WELL_A']
        ai, vpvs = samples['WELL_A']
        vp, vs, rho = (data[_x].to(_u).magnitude for _x, _u in
                       [('vp_dry', 'm/s'), ('vs_dry', 'm/s'), ('rho_dry', 'g/cm**3')])
        np.testing.assert_allclose(vp * rho / 1000., ai)  # In km/s*g/cm3
        np.testing.assert_allclose(vp / vs, vpvs)
        self.assertEqual(sum(len(samples[_w][0]) for _w in result.well_names), len(samples['All'][0]))

    def test_ai_and_vpvs_needs_all_logs(self):
        no_vs = {_k: _v for _k, _v in log_table.items() if _k != 'S velocity'}
        stats = StatsCalculation(self.wells, self.wis, ['Sand F'], no_vs, {'Volume': ['<', 0.5]})
        results = stats.run()
        self.assertEqual({}, results['Sand F'].ai_and_vpvs())

        # An empty panel, and a warning
        with self.assertLogs('blixt_geo_py.analysis.calc_statistics', level='WARNING') as logs:
            fig = stats.plot_elastics(results, file_name=None)
        self.assertIn('Sand F', logs.output[0])
        self.assertEqual(0, len(fig.axes[0].containers))
        self.assertEqual(0, len(fig.legends))
        show_or_close()

    def test_ai_and_vpvs_with_zero_vs(self):
        result = IntervalStats('Sand', LogTable(log_table), Cutoffs(), per_well={'W': {
            'vp_dry': Q_(np.array([3000., 3000.]), 'm/s'), 'vs_dry': Q_(np.array([1500., 0.]), 'm/s'),
            'rho_dry': Q_(np.array([2., 2.]), 'g/cm**3')}})
        ai, vpvs = result.ai_and_vpvs()['W']
        np.testing.assert_allclose([6., 6.], ai)
        self.assertAlmostEqual(2., vpvs[0])
        self.assertFalse(np.isfinite(vpvs[1]))

    def test_plot_elastics(self):
        stats = StatsCalculation(self.wells, self.wis, wi_sands + wi_shales, log_table, {'Volume': ['<', 0.5]})
        results = stats.run()
        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            fig = stats.plot_elastics(results)
            self.assertTrue(os.path.isfile(os.path.join(tmp_dir, 'elastics.png')))

        # A panel per interval, in a grid like plot_gardner()
        self.assertEqual(6, len(fig.axes))
        self.assertFalse(fig.axes[5].get_visible())
        self.assertEqual('Sand F', fig.axes[0].get_title(loc='left'))
        self.assertEqual('Vp/Vs', fig.axes[0].get_ylabel())
        for _i in [2, 3, 4]:
            self.assertEqual('Acoustic impedance [km/s*g/cm3]', fig.axes[_i].get_xlabel())

        # The mean of each well, in the style of the well, and no regression lines
        ax = fig.axes[0]
        samples = results['Sand F'].ai_and_vpvs()
        wells = [_w for _w in samples if _w != 'All']
        self.assertEqual(len(wells), len(ax.containers))
        self.assertEqual([], [_l for _l in ax.get_lines() if len(_l.get_xdata()) > 1])
        all_wells = [_w.name for _w in stats.wells]
        for well_name, container in zip(wells, ax.containers):
            color, marker = stats.well_style(well_name, all_wells.index(well_name))
            line = container.lines[0]
            self.assertEqual(marker, line.get_marker())
            self.assertEqual(color, line.get_color())
            ai, vpvs = samples[well_name]
            self.assertAlmostEqual(np.nanmean(ai), line.get_xdata()[0])
            self.assertAlmostEqual(np.nanmean(vpvs), line.get_ydata()[0])
        labels = [_t.get_text() for _t in fig.legends[0].get_texts()]
        for _label in wells + ['All wells']:
            self.assertIn(_label, labels)
        show_or_close()

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
        for _constant in [1., 0.1, 2.5, 3456.7]:
            self.assertEqual(0., linear_depth_trend(np.full(10, _constant), np.arange(10.))['r2'])

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
        With more than max_intervals intervals, the plot is split into several figures, keeping the order.
        max_intervals is given explicitly, so that the test doesn't depend on its default
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
            figs = stats.plot_logs_vs_burial_depth(results, max_intervals=5)
            self.assertEqual(['logs_vs_burial_depth_1.png', 'logs_vs_burial_depth_2.png'], sorted(os.listdir(tmp_dir)))
            self.assertEqual([5 * n_logs, n_logs], [len(_f.axes) for _f in figs])
            self.assertIn('Sand F, first', y_labels(figs[0])[0])
            self.assertIn('Sand F, last', y_labels(figs[1])[0])
            show_or_close()

        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            # Exactly five intervals fit in one figure, whose file name has no number
            five = dict(list(results.items())[:5])
            self.assertEqual(1, len(stats.plot_logs_vs_burial_depth(five, max_intervals=5)))
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
                                 {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}, project_to_burial_depth=None)
        results = stats.run()

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output(results, file_name)
            open_for_inspection(file_name, 'SumsAndAverages_unit_test.xlsx')
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

    def test_project_to_burial_depth(self):
        """
        With project_to_burial_depth, there are extra statistics of the samples moved along the linear trends, and
        the burial depth plot marks where the trends cross that depth
        """
        _cutoffs = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}
        target = Q_(2., 'km')
        stats = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, _cutoffs, project_to_burial_depth=target)
        results = stats.run()
        interval = results['Sand F']
        self.assertEqual('Projected to 2000 m', interval.projected_label)

        # The mean is where the trend crosses the depth, and the spread is the one around the trend
        summary = stats.summary(results)
        rows = summary[summary['well'] == interval.projected_label].set_index('log')
        self.assertEqual(len(log_table), len(rows))
        for _log in log_table.values():
            trend = interval.burial_depth_trend(_log)
            self.assertAlmostEqual(trend['slope'] * 2000. + trend['intercept'], rows.loc[_log, 'mean'], places=6)
            self.assertAlmostEqual(trend['std_detrended'], rows.loc[_log, 'std'], places=6)
            self.assertEqual(trend['n'], rows.loc[_log, 'n'])

        # Without the input, everything is as before
        plain_stats = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, _cutoffs)
        plain_results = plain_stats.run()
        self.assertEqual({}, plain_results['Sand F'].projected())
        pd.testing.assert_frame_equal(plain_stats.summary(plain_results),
                                      summary[summary['well'] != interval.projected_label].reset_index(drop=True))

        # One extra line in the RokDoc output
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output(results, file_name)
            lines = {_l['Name']: _l for _l in read_rokdoc_lines(file_name)}
        line = lines['Sand F_projected_2000m']
        self.assertEqual(2 + len(interval.per_well), len(lines))
        self.assertEqual('NONE', line['Well'])
        self.assertAlmostEqual(rows.loc[log_table['P velocity'], 'mean'], line['VpMean'], places=6)

        # A vertical and a horizontal dashed line, for each log
        fig = stats.plot_logs_vs_burial_depth(results, file_name=None)
        fig = fig[0] if isinstance(fig, list) else fig
        for _ax, _log in zip(fig.axes, interval.log_table.log_names):
            dashed = [_l for _l in _ax.get_lines() if _l.get_linestyle() == '--']
            self.assertEqual(2, len(dashed))
            vertical, horizontal = dashed
            self.assertAlmostEqual(rows.loc[_log, 'mean'], vertical.get_xdata()[0], places=6)
            self.assertAlmostEqual(2000., horizontal.get_ydata()[0])
            self.assertIn('2000 m', [_t.get_text() for _t in _ax.texts])
        stats.plot_averages(results)
        show_or_close()

    def test_projected_per_well(self):
        """
        Each sample of a well is moved along the trend through all wells, and together they make up projected()
        """
        stats = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, {'Volume': ['<', 0.5]},
                                 project_to_burial_depth=Q_(2000., 'm'))
        interval = stats.run()['Sand F']
        per_well = interval.projected_per_well()
        self.assertEqual(sorted(interval.burial_depth), sorted(per_well))
        vp_log = log_table['P velocity']
        trend = interval.burial_depth_trend(vp_log)
        for _well, _data in per_well.items():
            depth = interval.burial_depth[_well].to('m').magnitude
            np.testing.assert_allclose(interval.per_well[_well][vp_log].magnitude + trend['slope'] * (2000. - depth),
                                       _data[vp_log].magnitude)
        np.testing.assert_allclose(np.concatenate([_d[vp_log].magnitude for _d in per_well.values()]),
                                   interval.projected()[vp_log].magnitude)

    def test_plot_gardner_and_elastics_projected(self):
        """
        With project_to_burial_depth, plot_gardner() and plot_elastics() also plot the projected data, of the
        intervals that have a burial depth to project to
        """
        _cutoffs = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                 project_to_burial_depth=[Q_(2000., 'm'), None])
        results = stats.run()
        interval = results['Sand F']

        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.working_dir = tmp_dir
            gardner_figs = stats.plot_gardner(results)
            elastics_figs = stats.plot_elastics(results)
            self.assertEqual(['elastics.png', 'elastics_projected.png', 'gardner.png', 'gardner_projected.png'],
                             sorted(os.listdir(tmp_dir)))

        for figs in [gardner_figs, elastics_figs]:
            self.assertEqual(2, len(figs))
            # Both intervals in the first figure, and only the projected one in the second
            self.assertEqual(2, len([_ax for _ax in figs[0].axes if _ax.get_visible()]))
            projected_axes = [_ax for _ax in figs[1].axes if _ax.get_visible()]
            self.assertEqual(1, len(projected_axes))
            self.assertIn('Sand F, projected to 2000 m', projected_axes[0].get_title(loc='left'))
            self.assertNotIn('projected', figs[0].axes[0].get_title(loc='left'))

        # The calibration in the projected figure is that of the projected data
        vp, rho = interval.vp_and_rho(projected=True)['All']
        fit = fit_gardner(vp, rho)
        self.assertIn('a = {:.3f}, b = {:.3f}'.format(fit['a'], fit['b']),
                      gardner_figs[1].axes[0].get_title(loc='left'))
        self.assertNotEqual(fit_gardner(*interval.vp_and_rho()['All'])['a'], fit['a'])

        # The Gardner table holds the same calibration, only for the projected interval, and it can be read back
        table = stats.gardner(results)
        projected_rows = table[table['well'].str.startswith('Projected')]
        self.assertEqual(['Sand F'], list(projected_rows['interval']))
        self.assertEqual(['Projected to 2000 m'], list(projected_rows['well']))
        self.assertAlmostEqual(fit['a'], projected_rows['a'].iloc[0])
        self.assertAlmostEqual(fit['b'], projected_rows['b'].iloc[0])
        self.assertEqual(int(np.sum(np.isfinite(vp) & np.isfinite(rho) & (vp > 0.) & (rho > 0.))),
                         projected_rows['n'].iloc[0])
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'gardner.xlsx')
            stats.save_gardner(results, file_name)
            a, b = read_gardner(file_name, 'Sand F', well='Projected to 2000 m')
        self.assertAlmostEqual(fit['a'], a)
        self.assertAlmostEqual(fit['b'], b)

        # Without any projection, a single figure as before
        plain_stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs)
        plain_results = plain_stats.run()
        self.assertIsInstance(plain_stats.plot_gardner(plain_results, file_name=None), plt.Figure)
        self.assertIsInstance(plain_stats.plot_elastics(plain_results, file_name=None), plt.Figure)
        show_or_close()

    def test_project_to_burial_depth_per_interval(self):
        """
        Each working interval has its own burial depth, and None leaves the projection out for that interval
        """
        _cutoffs = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                 project_to_burial_depth=[Q_(2000., 'm'), None])
        results = stats.run()
        self.assertEqual(Q_(2000., 'm'), results['Sand F'].project_to_burial_depth)
        self.assertIsNone(results['Sand E'].project_to_burial_depth)
        self.assertEqual({}, results['Sand E'].projected())
        summary = stats.summary(results)
        projected_rows = summary[summary['well'].str.startswith('Projected')]
        self.assertEqual({'Sand F'}, set(projected_rows['interval']))
        self.assertEqual({'Projected to 2000 m'}, set(projected_rows['well']))

        # A pint Quantity array is taken as a list
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                 project_to_burial_depth=Q_([2.0, 2.1], 'km'))
        results = stats.run()
        self.assertEqual(['Projected to 2000 m', 'Projected to 2100 m'],
                         [_r.projected_label for _r in results.values()])

        # A single value is used in all intervals
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                 project_to_burial_depth=Q_(2000., 'm'))
        self.assertEqual([Q_(2000., 'm')] * 2, stats.project_to_burial_depths)

    def test_project_to_burial_depth_must_be_a_length(self):
        for _wrong in [2000., Q_(2000., 'm/s'), [Q_(2000., 'm'), 2000.]]:
            with self.assertRaises(ValueError):
                StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table,
                                 project_to_burial_depth=_wrong)
        # One burial depth per working interval
        with self.assertRaises(ValueError):
            StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table,
                             project_to_burial_depth=[Q_(2000., 'm')])

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
            saved = pd.read_excel(file_name, sheet_name='summary')
            saved_correlations = pd.read_excel(file_name, sheet_name='correlations')

        correlations = stats.correlations(results)
        self.assertEqual(list(correlations.columns), list(saved_correlations.columns))
        np.testing.assert_allclose(correlations['r'], saved_correlations['r'])

        self.assertEqual(list(summary.columns), list(saved.columns))
        self.assertEqual(len(summary), len(saved))
        np.testing.assert_allclose(summary['mean'], saved['mean'])
        # An interval without samples has no statistics
        empty = saved[(saved['interval'] == 'Sand D') & (saved['well'] == 'WELL_B')]
        self.assertTrue((empty['n'] == 0).all())
        self.assertTrue(empty['mean'].isna().all())

    def test_exclude(self):
        """
        A log type can be left out of one well and interval, without affecting the other logs, wells or intervals
        """
        _cutoffs = {'Volume': ['<', 0.5]}
        plain = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs).run()
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                 exclude=('well_f', 'sand e', 'S velocity'))  # Not case sensitive
        results = stats.run()
        self.assertGreater(len(plain['Sand E'].per_well['WELL_F']['vs_dry']), 0)
        self.assertNotIn('vs_dry', results['Sand E'].per_well['WELL_F'])
        # The other logs keep the same samples
        np.testing.assert_array_equal(results['Sand E'].per_well['WELL_F']['vp_dry'].magnitude,
                                      plain['Sand E'].per_well['WELL_F']['vp_dry'].magnitude)
        # The other interval, and the other wells, are untouched
        self.assertIn('vs_dry', results['Sand F'].per_well['WELL_F'])
        other_wells = [_w for _w in results['Sand E'].well_names if _w != 'WELL_F']
        self.assertGreater(len(other_wells), 0)
        for _well in other_wells:
            self.assertEqual(set(results['Sand E'].per_well[_well]), set(plain['Sand E'].per_well[_well]))

        summary = stats.summary(results)
        rows = summary[(summary['interval'] == 'Sand E') & (summary['log type'] == 'S velocity')]
        self.assertNotIn('WELL_F', set(rows['well']))
        # 'All' no longer holds the S velocity of WELL_F
        n_all = rows[rows['well'] == 'All']['n'].iloc[0]
        plain_summary = stats.summary(plain)
        plain_rows = plain_summary[(plain_summary['interval'] == 'Sand E') &
                                   (plain_summary['log type'] == 'S velocity')]
        n_well_f = plain_rows[plain_rows['well'] == 'WELL_F']['n'].iloc[0]
        self.assertEqual(n_all, plain_rows[plain_rows['well'] == 'All']['n'].iloc[0] - n_well_f)
        # Without the S velocity, WELL_F has no elastics in Sand E, but still a Gardner calibration
        self.assertNotIn('WELL_F', results['Sand E'].ai_and_vpvs())
        self.assertIn('WELL_F', results['Sand E'].vp_and_rho())

        # All the outputs work with an excluded log
        stats.plot_logs_vs_depth(results, file_name=None)
        stats.plot_averages(results)
        stats.plot_logs_vs_burial_depth(results, file_name=None)
        stats.plot_gardner(results, file_name=None)
        stats.plot_elastics(results, file_name=None)
        with tempfile.TemporaryDirectory() as tmp_dir:
            stats.save_rokdoc_output(results, os.path.join(tmp_dir, 'SumsAndAverages.xlsx'))
        show_or_close()

    def test_exclude_wildcards_and_suffixes(self):
        _cutoffs = {'Volume': ['<', 0.5]}
        # None as log type leaves the well out of the interval
        results = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                   exclude=[('WELL_F', 'Sand E', None)]).run()
        self.assertNotIn('WELL_F', results['Sand E'].well_names)
        self.assertIn('WELL_F', results['Sand F'].well_names)
        # None as interval leaves the log out of all intervals
        results = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, _cutoffs,
                                   exclude=[('WELL_F', None, 'Density')]).run()
        for _stats in results.values():
            self.assertNotIn('rho_dry', _stats.per_well['WELL_F'])
            self.assertIn('vp_dry', _stats.per_well['WELL_F'])
        # The label of a repeated interval only excludes from that run, its name from all of them
        sand, shale = {'Volume': ['<', 0.5]}, {'Volume': ['>', 0.5]}
        for _interval, _expected in [('Sand F, sand', {'Sand F, sand'}), ('Sand F', {'Sand F, sand', 'Sand F, shale'})]:
            with self.subTest(interval=_interval):
                results = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand F'], log_table, [sand, shale],
                                           ['sand', 'shale'], exclude=[('WELL_F', _interval, 'S velocity')]).run()
                self.assertEqual(_expected, {_k for _k, _s in results.items() if 'vs_dry' not in _s.per_well['WELL_F']})

    def test_pair_correlation(self):
        rng = np.random.default_rng(1)
        x = rng.normal(0., 1., 200)
        y = 2. * x + rng.normal(0., 0.5, 200)
        r, n = pair_correlation(x, y)
        self.assertAlmostEqual(np.corrcoef(x, y)[0, 1], r)
        self.assertEqual(200, n)
        # NaNs in either array are skipped pairwise
        x[:10], y[10:20] = np.nan, np.nan
        r, n = pair_correlation(x, y)
        self.assertEqual(180, n)
        self.assertAlmostEqual(np.corrcoef(x[20:], y[20:])[0, 1], r)
        # Too few samples, or a constant, gives NaN
        self.assertTrue(np.isnan(pair_correlation(np.array([1., 2.]), np.array([1., 3.]))[0]))
        self.assertTrue(np.isnan(pair_correlation(np.ones(10), np.arange(10.))[0]))

    def test_correlations(self):
        stats = StatsCalculation(self.wells, self.wis, ['Sand F', 'Sand E'], log_table, {'Volume': ['<', 0.5]},
                                 project_to_burial_depth=Q_(2000., 'm'))
        results = stats.run()
        table = stats.correlations(results)
        sand_f = results['Sand F']
        # Three pairs, for each well, 'All', and the projected burial depth
        rows = table[table['interval'] == 'Sand F']
        self.assertEqual(3 * (len(sand_f.per_well) + 2), len(rows))
        self.assertEqual({('P velocity', 'S velocity'), ('P velocity', 'Density'), ('S velocity', 'Density')},
                         set(zip(rows['log type x'], rows['log type y'])))
        self.assertTrue(np.all(np.abs(rows['r'].dropna()) <= 1.))

        # The correlation of one well is that of its own samples
        well_f = sand_f.per_well['WELL_F']
        expected, n = pair_correlation(well_f['vp_dry'].magnitude, well_f['rho_dry'].magnitude)
        row = rows[(rows['well'] == 'WELL_F') & (rows['log type y'] == 'Density') &
                   (rows['log type x'] == 'P velocity')].iloc[0]
        self.assertAlmostEqual(expected, row['r'])
        self.assertEqual(n, row['n'])
        # 'All' pairs the samples of each well, also when one well lacks a log of the pair
        excluded = StatsCalculation(self.wells, self.wis, 'Sand F', log_table, {'Volume': ['<', 0.5]},
                                    exclude=('WELL_F', 'Sand F', 'S velocity')).run()['Sand F']
        vp, vs = excluded.paired('P velocity', 'S velocity')['All']
        self.assertEqual(len(vp), len(vs))
        self.assertNotIn('WELL_F', excluded.paired('P velocity', 'S velocity'))
        self.assertIn('WELL_F', excluded.paired('P velocity', 'Density'))
        all_rows = excluded.correlations()
        all_rows = all_rows[(all_rows['well'] == 'All') & (all_rows['log type y'] == 'S velocity')]
        self.assertAlmostEqual(pair_correlation(vp, vs)[0], all_rows['r'].iloc[0])

        # The RokDoc file holds the same correlations
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            stats.save_rokdoc_output({'Sand F': excluded}, file_name)
            lines = {_l['Name']: _l for _l in read_rokdoc_lines(file_name)}
        self.assertAlmostEqual(all_rows['r'].iloc[0], lines['Sand F']['VpVsCorrCoef'])
        self.assertEqual(-999.25, lines['WELL_F Sand F']['VpVsCorrCoef'])
        vp_rho = excluded.correlations()
        vp_rho = vp_rho[(vp_rho['well'] == 'WELL_F') & (vp_rho['log type x'] == 'P velocity') &
                        (vp_rho['log type y'] == 'Density')]
        self.assertAlmostEqual(vp_rho['r'].iloc[0], lines['WELL_F Sand F']['VpRhoCorrCoef'])

    def test_correlations_need_the_log_types(self):
        _log_table = {_k: _v for _k, _v in log_table.items() if _k != 'S velocity'}
        results = StatsCalculation(self.wells, self.wis, 'Sand F', _log_table, {'Volume': ['<', 0.5]}).run()
        table = results['Sand F'].correlations()
        self.assertEqual({('P velocity', 'Density')}, set(zip(table['log type x'], table['log type y'])))

    def test_exclude_input_checks(self):
        for _exclude in ['WELL_F', ('WELL_F', 'Sand E'), [('WELL_F', 'Sand E', 1)]]:
            with self.subTest(exclude=_exclude):
                with self.assertRaises(TypeError):
                    StatsCalculation(self.wells, self.wis, 'Sand E', log_table, exclude=_exclude)
        # Misspelled names are caught
        for _exclude in [('WELL_X', 'Sand E', 'S velocity'), ('WELL_F', 'Sand X', 'S velocity'),
                         ('WELL_F', 'Sand E', 'Shear velocity'), (None, None, None)]:
            with self.subTest(exclude=_exclude):
                with self.assertRaises(ValueError):
                    StatsCalculation(self.wells, self.wis, 'Sand E', log_table, exclude=_exclude)


if __name__ == '__main__':
    unittest.main()
