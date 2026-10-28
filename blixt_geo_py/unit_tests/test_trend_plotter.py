import unittest

import matplotlib.pyplot as plt

from blixt_geo_py.plotting.trend_plotter import TrendPlotter
from blixt_geo_py.unit_tests.test_cross_plotter import make_data_sources


class TestCases(unittest.TestCase):

    def test_data_cds(self):
        ds1, ds2, wis, coffs = make_data_sources()

        tp = TrendPlotter({str(_s.name):_s for _s in [ds1, ds2]},
                          x='md',
                          y='var_two',
                          cutoffs=coffs,
                          working_intervals=wis,
                          project_table="C:\\Users\\emb\\Downloads\\Book.xlsx")

        d_cds = tp.cds

        return tp.draw(d_cds)

    def test_calc_trend(self):
        ds1, ds2, wis, coffs = make_data_sources()

        tp = TrendPlotter({str(_s.name):_s for _s in [ds1, ds2]},
                          x='md',
                          y='var_two',
                          cutoffs=coffs,
                          working_intervals=wis)
        cds = tp.cds
        tp.calc_trend('md', 'var_two', cds, verbose=True)

        plt.show()
