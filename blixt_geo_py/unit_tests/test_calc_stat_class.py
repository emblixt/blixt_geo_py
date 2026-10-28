import os
import unittest

import matplotlib.pyplot as plt
import numpy as np

from blixt_geo_py import Q_
from blixt_geo_py.core.core import Cutoffs, CutoffRule, LogTable
from blixt_geo_py.core.project import Project
from blixt_geo_py.utils.calc_stat_class import (IntervalStats, StatsCalculation, break_at_gaps,
                                                collect_interval_stats, isolated_samples, to_cutoffs)

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))
project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')

log_table = {'P velocity': 'vp_dry', 'S velocity': 'vs_dry', 'Density': 'rho_dry', 'Porosity': 'phie',
             'Volume': 'vcl'}
wi_sands = ['Sand F', 'Sand E', 'Sand D']
wi_shales = ['Shale G', 'Shale C']

# Set to True, or set the environment variable BLIXT_SHOW_PLOTS=1, to view the plots created by the tests.
# Off by default, so running the whole test suite doesn't stop at every plot window
show_plots = os.environ.get('BLIXT_SHOW_PLOTS', '0') == '1'

def show_or_close():
    if show_plots:
        plt.show()
    else:
        plt.close('all')


def make_project():
    wp = Project(name='MyProject', project_table=project_table)
    wp.load_all_wells()
    assert wp.wells is not None, 'No wells loaded from {}'.format(project_table)
    return wp, wp.wells, wp.load_all_wis()


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
        stats = StatsCalculation(self.wells, self.wis, wi_sands, {'Volume': ['<', 0.5]}, log_table, 'sands')
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
            StatsCalculation(self.wells, self.wis, wi_sands, [{'Volume': ['<', 0.5]}], log_table)
        with self.assertRaises(TypeError):
            StatsCalculation(['WELL_F'], self.wis, wi_sands, None, log_table)

    def test_calc_stat(self):
        cutoffs_sands = {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}
        cutoffs_shales = {'Volume': ['>', 0.5], 'Porosity': ['<', 0.1]}
        stats = StatsCalculation(
            self.wells, self.wis, wi_sands + wi_shales,
            [cutoffs_sands] * len(wi_sands) + [cutoffs_shales] * len(wi_shales),
            log_table,
            ['sands'] * len(wi_sands) + ['shales'] * len(wi_shales),
            )
        results = stats.run()
        stats.plot_logs_vs_depth(results, file_name=None)
        figs = stats.plot_averages(results)
        self.assertEqual(list(figs.keys()), list(log_table.keys()))
        print(stats.summary(results).to_string())
        show_or_close()


if __name__ == '__main__':
    unittest.main()
