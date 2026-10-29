"""
Tests of the masking of well logs, using the current Well API

A mask is calculated from a set of rules, Cutoffs, which is a list of CutoffRule objects. Each CutoffRule masks out the
samples of one log that are not within the given limits, e.g. CutoffRule('phie', '<', Q_(0.1, '')) only keeps the
samples where the porosity is below 0.1. The masks of the rules are combined with AND.

Well.dict(cutoffs=...) returns a dictionary of log name: log data, plus the combined mask under the key 'mask'.
With use_cutoffs=False all samples are kept, and with use_cutoffs=True the mask is applied to all logs.
"""
import os
import unittest

import numpy as np

from blixt_geo_py import Q_
from blixt_geo_py.core.core import Cutoffs, CutoffRule, Interval, Intervals, LogTable, StratUnit
from blixt_geo_py.core.project import Project
from blixt_geo_py.core.well import Well

# Tops in Well A, in meters MD
tops = {'TOP A': 408.0,
        'TOP B': 1560.0,
        'TOP C': 1585.0,
        'TOP D': 1826.0,
        'TOP E': 1878.0,
        'TOP F': 1984.0,
        'BASE F': 2158.0,
        'TOP G': 2158.0,
        'TOP H': 2211.0,
        'BASE H': 2365.0,
        'TOP I': 2365.0,
        'TOP J': 2452.0}

# Working intervals in Well A, as top and base in meters MD
working_intervals = {
    'SAND C': [1585.0, 1826.0],
    'SHALE C': [1585.0, 1826.0],
    'SAND D': [1826.0, 1878.0],
    'SAND E': [1878.0, 1984.0],
    'SAND F': [1984.0, 2158.0],
    'SHALE G': [2158.0, 2211.0],
    'SAND H': [2211.0, 2365.0]
}


def depth_rule(top: float, base: float) -> CutoffRule:
    """
    Returns a CutoffRule that only keeps the samples between top and base, given in meters MD
    """
    return CutoffRule('md', '><', [Q_(top, 'm'), Q_(base, 'm')])


class MasksTestCase(unittest.TestCase):
    lmt = 0.1  # porosity limit used in most tests

    @classmethod
    def setUpClass(cls):
        wp = Project(name='MyProject', log_to_stdout=True)

        # Only read the logs we need. The log table also tells which log to use for each log type, which is used
        # when the cutoffs are given by log type, e.g. 'Porosity', instead of log name, e.g. 'phie'
        cls.log_table = LogTable({'Porosity': 'phie', 'Volume': 'vcl'})
        cls.w = Well()
        cls.w.read_las(os.path.join(wp.working_dir, 'test_data', 'Well A.las'), log_table=cls.log_table)
        # The md log is needed for the masks that use tops or working intervals
        cls.w.create_md_log()

        cls.wis = Intervals(intervals=[
            Interval(cls.w.name, Q_(top, 'm'), Q_(base, 'm'), StratUnit(wi_name, 1))
            for wi_name, (top, base) in working_intervals.items()])

        # All samples of the porosity and depth, without any mask, as plain numpy arrays
        data = cls.w.dict()
        cls.phie = data['phie'].magnitude
        cls.md = data['md'].to('m').magnitude

    def mask_of(self, rules: list) -> np.ndarray:
        """
        Returns the mask that the given list of CutoffRules creates in the well
        """
        return self.w.dict(cutoffs=Cutoffs(cutoffs=rules), use_cutoffs=False)['mask']

    def test_mask_by_log_name(self):
        # The mask should keep exactly those samples where phie < lmt
        msk = self.mask_of([CutoffRule('phie', '<', Q_(self.lmt, ''))])
        with self.subTest('length'):
            self.assertEqual(np.sum(self.phie < self.lmt), np.sum(msk))
        with self.subTest('value'):
            self.assertLess(np.nanmax(self.phie[msk]), self.lmt)

    def test_mask_by_log_type(self):
        # Cutoffs given by log type are converted to log names with the log table, and should give the same mask as
        # when the log name is used directly
        cutoffs = Cutoffs(cutoffs=[CutoffRule('Porosity', '<', Q_(self.lmt, ''))]).use_log_table(self.log_table)
        self.assertEqual(['phie'], cutoffs.cutoff_params)
        msk = self.w.dict(cutoffs=cutoffs, use_cutoffs=False)['mask']
        np.testing.assert_array_equal(self.mask_of([CutoffRule('phie', '<', Q_(self.lmt, ''))]), msk)

    def test_mask_with_tops(self):
        # Combine the porosity cutoff with a depth range from TOP C to BASE F
        msk = self.mask_of([CutoffRule('phie', '<', Q_(self.lmt, '')), depth_rule(tops['TOP C'], tops['BASE F'])])
        with self.subTest('value'):
            self.assertLess(np.nanmax(self.phie[msk]), self.lmt)
        with self.subTest('depth'):
            self.assertGreaterEqual(self.md[msk].min(), tops['TOP C'])
            self.assertLessEqual(self.md[msk].max(), tops['BASE F'])

    def test_empty_cutoffs(self):
        # Without any rules, all samples are kept
        msk = self.mask_of([])
        self.assertEqual(len(self.phie), np.sum(msk))

    def test_missing_log(self):
        # A rule for a log that does not exist in the well is ignored with a warning, it does not raise an error
        cutoffs = Cutoffs(cutoffs=[CutoffRule('Saturation', '<', Q_(self.lmt, ''))]).use_log_table(self.log_table)
        msk = self.w.dict(cutoffs=cutoffs, use_cutoffs=False)['mask']
        self.assertTrue(msk.all())

    def test_mask_with_working_interval(self):
        # The working interval is turned into a depth rule, which is combined with the porosity cutoff
        interval = self.wis.get_interval('SAND E', self.w.name)
        self.assertIsNotNone(interval)
        interval_rule = CutoffRule('md', '><', [interval.top, interval.base])
        top, base = working_intervals['SAND E']

        msk = self.mask_of([CutoffRule('phie', '<', Q_(self.lmt, '')), interval_rule])
        with self.subTest('value'):
            self.assertLess(np.nanmax(self.phie[msk]), self.lmt)
        with self.subTest('depth'):
            self.assertGreaterEqual(self.md[msk].min(), top)
            self.assertLessEqual(self.md[msk].max(), base)

        # Without the porosity cutoff, the mask should cover the whole working interval
        msk = self.mask_of([interval_rule])
        with self.subTest('whole interval'):
            self.assertEqual(np.sum((self.md > top) & (self.md < base)), np.sum(msk))

    def test_apply_mask(self):
        # With use_cutoffs=True the mask is applied to all logs, so only the masked samples are returned
        data = self.w.dict(cutoffs=Cutoffs(cutoffs=[CutoffRule('phie', '<', Q_(self.lmt, ''))]), use_cutoffs=True)
        m_phie = data['phie'].magnitude
        with self.subTest('length'):
            self.assertEqual(np.sum(self.phie < self.lmt), len(m_phie))
        with self.subTest('value'):
            self.assertLess(np.nanmax(m_phie), self.lmt)
        with self.subTest('all logs'):
            for _key, _values in data.items():
                self.assertEqual(len(m_phie), len(_values), _key)

        # The same, using a working interval, should only return samples within it
        interval = self.wis.get_interval('Sand F', self.w.name)
        data = self.w.dict(cutoffs=Cutoffs(cutoffs=[CutoffRule('md', '><', [interval.top, interval.base])]),
                           use_cutoffs=True)
        top, base = working_intervals['SAND F']
        depths = data['md'].to('m').magnitude
        with self.subTest('interval'):
            self.assertGreaterEqual(depths.min(), top)
            self.assertLessEqual(depths.max(), base)

    def test_append_mask(self):
        # Rules added to Cutoffs with append() are combined with AND with the existing rules
        lmt1 = 0.05
        lmt2 = 0.4
        vcl = self.w.dict()['vcl'].magnitude

        cutoffs = Cutoffs(cutoffs=[CutoffRule('phie', '>', Q_(lmt1, ''))])
        msk = self.w.dict(cutoffs=cutoffs, use_cutoffs=False)['mask']
        with self.subTest('first rule'):
            self.assertGreater(np.nanmin(self.phie[msk]), lmt1)

        cutoffs.append(CutoffRule('vcl', '<', Q_(lmt2, '')))
        msk = self.w.dict(cutoffs=cutoffs, use_cutoffs=False)['mask']
        with self.subTest('both rules'):
            self.assertGreater(np.nanmin(self.phie[msk]), lmt1)
            self.assertLess(np.nanmax(vcl[msk]), lmt2)
        with self.subTest('length'):
            self.assertEqual(np.sum((self.phie > lmt1) & (vcl < lmt2)), np.sum(msk))


if __name__ == '__main__':
    unittest.main()
