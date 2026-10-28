import os
import unittest

import numpy as np
from bokeh.plotting import show, row, column

from blixt_geo_py import Q_
from blixt_geo_py.core.core import Intervals, Cutoffs
from blixt_geo_py.plotting.rp_plotter import RockPhysicsPlotter

test_file_dir = str(os.path.dirname(__file__).replace(
    'blixt_geo_py\\unit_tests',
    'test_data'))
las_fileA = os.path.join(test_file_dir, "Well A.las")


def make_wells():
    from blixt_geo_py.core.well import Well, Depth
    from blixt_geo_py.core.log_curve import LogCurve
    from blixt_geo_py.core.core import CutoffRule, Interval, StratUnit, Header
    # Create new test data "from" two wells:
    n1 = 800
    md1 = Q_(np.linspace(1000., 2000., n1), 'm')
    vp1 = Q_(np.random.normal(0, 20, n1) + np.linspace(2000, 3000, n1), 'm/s')
    vs1 = Q_(np.random.normal(0, 10, n1) + np.linspace(1500, 2500, n1), 'm/s')
    rho1 = Q_(np.random.normal(0, 0.2, n1) + np.linspace(2.5, 3.5, n1), 'g/cc')
    phie1 = Q_(np.clip(np.random.normal(0.2, 0.05, n1), 0, 1), '')
    vcl1 = Q_(np.clip(np.random.normal(0.5, 0.15, n1), 0, 1), '')
    # data_one = dict(md=md1, vp=vp1, vs=vs1, rho=rho1, phie=phie1, vcl=vcl1)
    # ds1 = xp.DataSource(name='Well A', data=data_one)
    w1 = Well(Header(dict(name='Well A')), [
        LogCurve('vp', vp1, Depth(md1)),
        LogCurve('vs', vs1, Depth(md1)),
        LogCurve('rho', rho1, Depth(md1)),
        LogCurve('phie', phie1, Depth(md1)),
        LogCurve('vcl', vcl1, Depth(md1))
    ])

    n2 = 800
    md2 = Q_(np.linspace(1500., 3500., n2), 'm')
    vp2 = Q_(np.random.normal(0, 20, n2) + np.linspace(2000, 3500, n2), 'm/s')
    vs2 = Q_(np.random.normal(0, 10, n2) + np.linspace(1500, 2800, n2), 'm/s')
    rho2 = Q_(np.random.normal(0, 0.2, n2) + np.linspace(2.5, 3.9, n2), 'g/cc')
    phie2 = Q_(np.clip(np.random.normal(0.2, 0.05, n2), 0, 1), '')
    vcl2 = Q_(np.clip(np.random.normal(0.5, 0.15, n2), 0, 1), '')
    # data_two = dict(md=md2, vp=vp2, vs=vs2, rho=rho2, phie=phie2, vcl=vcl2)
    # ds2 = xp.DataSource(name='Well B', data=data_two)
    w2 = Well(Header(dict(name='Well B')), [
        LogCurve('vp', vp2, Depth(md2)),
        LogCurve('vs', vs2, Depth(md2)),
        LogCurve('rho', rho2, Depth(md2)),
        LogCurve('phie', phie2, Depth(md2)),
        LogCurve('vcl', vcl2, Depth(md2))
    ])

    rule1 = CutoffRule('phie', '>', Q_(0.1, ''))
    rule2 = CutoffRule('vcl', '<', Q_(0.5, ''))
    cutoffs = Cutoffs(cutoffs=[rule1, rule2])

    wis = Intervals(
        name='test', intervals=[
            Interval( well='Well A', top=Q_(1350, 'm'), base=Q_(1450, 'm'), interval_info=StratUnit('Cook FM', 1)),
            Interval( well='Well A', top=Q_(1550, 'm'), base=Q_(1750, 'm'), interval_info=StratUnit('Oseberg FM', 1)),
            Interval( well='Well B', top=Q_(1500, 'm'), base=Q_(1900, 'm'), interval_info=StratUnit('Cook FM', 1)),
            Interval( well='Well B', top=Q_(1900, 'm'), base=Q_(2450, 'm'), interval_info=StratUnit('Oseberg FM', 1)),
            Interval(well='Well B', top=Q_(2450, 'm'), base=Q_(3500, 'm'), interval_info=StratUnit('Drake FM', 1))
        ] )

    return w1, w2, wis, cutoffs


class TestCases(unittest.TestCase):
    def test_data_cds(self, unit_test=True):
        from blixt_geo_py.core.core import LogTable
        w1, w2, wis, coffs = make_wells()

        lt1 = LogTable(name='standard', log_table={'P velocity': 'vp', 'S velocity': 'vs', 'Density': 'rho',
                                                   'Porosity': 'phie', 'Volume': 'vcl'})

        tp = RockPhysicsPlotter([w1, w2],
                                [lt1],
                                cutoffs=coffs,
                                working_intervals=wis,
                                )

        d_cds = tp.cds

        (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask,
         ct_guis, wis_guis, style_table,
         rpt_dt, add_row, var_select, delete_row, update_table) = tp.draw(d_cds)
        if unit_test:
            show(
                row(
                    column(
                        xplot,
                        row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask)
                    ),
                    column(style_table,
                           column(ct_guis[0], ct_guis[1]),
                           # ct_guis,
                           wis_guis
                           )
                )
            )
            return None
        else:
            return xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis, style_table

    def test_well(self, unit_test=True):
        from blixt_geo_py.core.well import Well
        from blixt_geo_py.core.core import LogTable, CutoffRule, Cutoffs
        from blixt_geo_py.rp.rp_wrapper import data_source_moduli

        w = Well()
        w.read_las(las_fileA, True)

        lt1 = LogTable(name='ptb5', log_table={'P velocity': 'vp_ptb5', 'S velocity': 'vs_ptb5', 'Density': 'rho_ptb5',
                                               'Porosity': 'phie', 'Volume': 'vcl'})
        lt2 = LogTable(name='so08', log_table={'P velocity': 'vp_so08', 'S velocity': 'vs_so08', 'Density': 'rho_so08',
                                               'Porosity': 'phie', 'Volume': 'vcl'})
        lt3 = LogTable(name='sg08', log_table={'P velocity': 'vp_sg08', 'S velocity': 'vs_sg08', 'Density': 'rho_sg08',
                                               'Porosity': 'phie', 'Volume': 'vcl'})

        rule1 = CutoffRule('phie', '>', Q_(0.1, ''))
        rule2 = CutoffRule('vcl', '<', Q_(0.4, ''))
        cutoffs = Cutoffs(cutoffs=[rule1, rule2])

        tp = RockPhysicsPlotter([w],
                                log_tables=[lt1, lt2, lt3],
                                cutoffs=cutoffs,
                                working_intervals=None,
                                )

        d_cds = tp.cds

        (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask,
         ct_guis,
         wis_guis, style_table,
         rpt_dt, add_row, var_select, delete__row, update_table) = tp.draw(d_cds)
        if unit_test:
            show(
                row(
                    column(
                        xplot,
                        row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask)
                    ),
                    column(style_table,
                           column(ct_guis[0], ct_guis[1]),
                           column(wis_guis)
                           )
                )
            )
        else:
            return xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis, style_table


    def test_well_with_rpt(self, unit_test=True):
        from blixt_geo_py.core.well import Well
        from blixt_geo_py.core.core import LogTable, CutoffRule, Cutoffs
        from blixt_geo_py.rp.rp_wrapper import (data_source_moduli, rpt_wrapper, rpt_to_moduli,
                                                rpt_phi_sw, return_rpt_keywords, RptVariableTable)

        w = Well()
        w.read_las(las_fileA, True)

        lt1 = LogTable(name='ptb5', log_table={'P velocity': 'vp_ptb5', 'S velocity': 'vs_ptb5', 'Density': 'rho_ptb5',
                                               'Porosity': 'phie', 'Volume': 'vcl'})
        lt2 = LogTable(name='so08', log_table={'P velocity': 'vp_so08', 'S velocity': 'vs_so08', 'Density': 'rho_so08',
                                                'Porosity': 'phie', 'Volume': 'vcl'})
        lt3 = LogTable(name='sg08', log_table={'P velocity': 'vp_sg08', 'S velocity': 'vs_sg08', 'Density': 'rho_sg08',
                                                'Porosity': 'phie', 'Volume': 'vcl'})

        # Parameters for plotting the rock physics template
        phi = Q_(np.linspace(0.05, 0.35, 4))
        sw = Q_([0.1, 0.5, 1.0], '')
        annotations = ['SW=0.1', 'SW=0.5', 'SW=1.0']

        rule1 = CutoffRule('phie', '>', Q_(0.1, ''))
        rule2 = CutoffRule('vcl', '<', Q_(0.4, ''))
        cutoffs = Cutoffs(cutoffs=[rule1, rule2])

        tp = RockPhysicsPlotter([w],
                                log_tables=[lt1, lt2, lt3],
                                cutoffs=cutoffs,
                                working_intervals=None,
                          )

        d_cds = tp.cds

        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis, style_table, \
            rpt_dt, add_row, var_select, delete_row, update_table = tp.draw(d_cds,
                                                                            rpt_variable=phi,
                                                                            rpt_constants=sw,
                                                                            rpt_function=rpt_phi_sw,
                                                                            rpt_annotations=annotations)

        # The below lines have/should have been implemented in RockPhysicsPlotter
        # rpt_table = RptVariableTable()
        # table_cds = rpt_table.cds

        # _vp, _vs, _rho = rpt_wrapper(phi, rpt_phi_sw, sw, return_rpt_keywords())
        # _dict = rpt_to_moduli(_vp, _vs, _rho, annotations)

        # rpt_lines_cds = ColumnDataSource(_dict)

        # rpt_dt, add_row, var_select, delete_row, update_table, rpt_lines_cds = rpt_table.draw(table_cds, rpt_lines_cds, t=phi, rpt=rpt_phi_sw, constants=sw, rpt_annotations=annotations)

        # # This doesn't work as intended. Add it to RockPhysicsPlotter
        # x_menu.value = 'ai'
        # y_menu.value = 'vp/vs'

        # xplot.multi_line(xs=x_menu.value, ys=y_menu.value, line_color='colors', line_width=3, legend_field='labels',
        #                  source=rpt_lines_cds)

        if unit_test:
            show(
                row(
                    column(
                        xplot,
                        row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask)
                    ),
                    column(style_table,
                           column(ct_guis[0], ct_guis[1]),
                           column(wis_guis)
                           )
                )
            )
        else:
            return (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis, style_table,
                    rpt_dt, add_row, var_select, delete_row, update_table)
