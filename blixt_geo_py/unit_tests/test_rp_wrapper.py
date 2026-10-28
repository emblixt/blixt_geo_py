import os
import unittest

from bokeh.models.sources import ColumnDataSource
import numpy as np

from blixt_geo_py import Q_
from blixt_geo_py.rp.rp_wrapper import (RptVariableTable, data_source_moduli, return_rpt_keywords, rpt_phi_sw,
                                        rpt_to_moduli, rpt_wrapper)

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))
test_file_dir = str(os.path.dirname(__file__).replace(
    'blixt_geo_py\\unit_tests',
    'test_data'))
las_fileA = os.path.join(test_file_dir, "Well A.las")


class TestCases(unittest.TestCase):

    def test_rpt_phi_sw(self):
        phi = Q_(0.2, ''); sw = Q_(0.1, '')
        print(rpt_phi_sw(phi, sw, **return_rpt_keywords()))
        phi = Q_(np.linspace(0.05, 0.3, 9), '')
        print(rpt_phi_sw(phi, sw, **return_rpt_keywords()))
        sw = Q_(np.linspace(0.1, 0.9, 9 ), '')
        print(rpt_phi_sw(phi, sw, **return_rpt_keywords()))

    def test_rpt_wrapper(self):
        phi = Q_(np.linspace(0.05, 0.35, 4))
        sw = [Q_(_x, '') for _x in [0.1, 0.5, 1.0]]
        v_p, v_s, rho = rpt_wrapper(phi, rpt_phi_sw, sw, return_rpt_keywords())
        for _i, _sw in enumerate(sw):
            print(_i, _sw)
            print(rho[_i])

    def test_data_source_moduli(self):
        from blixt_geo_py.core.well import Well
        from blixt_geo_py.core.core import LogTable
        from numpy import nanmin, nanmax
        w = Well()
        w.read_las(las_fileA, True)
        lt1 = LogTable(name='ptb5', log_table={'P velocity': 'vp_ptb5', 'S velocity': 'vs_ptb5', 'Density': 'rho_ptb5'})
        wds1 = w.data_source(log_table=lt1)
        data_source_moduli(wds1, lt1, verbose=True)
        for _key in list(wds1.keys()):
            print(_key, nanmin(wds1.data[_key]), nanmax(wds1.data[_key]))
        for _key in list(wds1.templates.keys()):
            print(_key)


    def test_rpt_to_moduli(self):
        from bokeh.plotting import figure, show
        from bokeh.models import ColumnDataSource
        from bokeh.io import output_file
        output_file(os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))

        phi = Q_(np.linspace(0.05, 0.35, 4))
        sw = Q_([0.1, 0.5, 1.0], '')
        annotations = ['SW=0.1', 'SW=0.5', 'SW=1.0']
        _vp, _vs, _rho = rpt_wrapper(phi, rpt_phi_sw, sw, return_rpt_keywords())
        _dict = rpt_to_moduli(_vp, _vs, _rho, annotations)

        source = ColumnDataSource(_dict)

        p = figure(title='Multi_Line test', width=400, height=400)
        p.multi_line(xs='ai', ys='vp/vs', line_color='colors', line_width=3, legend_field='labels', source=source)

        show(p)

    def test_rpt_table(self):
        table = RptVariableTable()
        cds = table.cds

        phi = Q_(np.linspace(0.05, 0.35, 4))
        sw = Q_([0.1, 0.5, 1.0], '')
        annotations = ['SW=0.1', 'SW=0.5', 'SW=1.0']
        _vp, _vs, _rho = rpt_wrapper(phi, rpt_phi_sw, sw, return_rpt_keywords())
        _dict = rpt_to_moduli(_vp, _vs, _rho, annotations)

        rpt_lines_cds = ColumnDataSource(_dict)

        return table.draw(cds, rpt_lines_cds, t=phi, rpt=rpt_phi_sw, constants=sw, rpt_annotations=annotations)
