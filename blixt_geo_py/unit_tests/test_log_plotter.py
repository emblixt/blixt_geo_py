import os
import unittest
from copy import deepcopy

import numpy as np
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure, show, row, column

from blixt_geo_py import Q_
from blixt_geo_py.core.seismic import SeismicTraces, test_data_length
from blixt_geo_py.plotting.log_plotter import (LogPlotter, LogColumn, Line, WellPlotter, create_column_figure,
                                               add_strat_table)

test_file_dir = str(os.path.dirname(__file__).replace(
    'blixt_geo_py\\unit_tests',
    'test_data'))


def make_test_data():
    # Builds some line objects using a common CDS
    from blixt_geo_py.unit_tests.test_cross_plotter import make_data_sources
    ds1, ds2, wis, cutoffs = make_data_sources()
    cds = ds1.cds
    line1 = Line(x='var_one', y='md', cds=cds, style=ds1.templates['var_one'])
    line2 = Line(x='var_two', y='md', cds=cds, style=ds1.templates['var_two'])
    line3 = Line(x='var_three', y='md', cds=cds, style=ds1.templates['var_three'])
    return cds, line1, line2, line3, wis, cutoffs

def make_well_data():
    from blixt_geo_py.core.well import Well
    from blixt_geo_py.core.core import LogTable, CutoffRule, Cutoffs
    project_table = os.path.join(test_file_dir.replace('test_data', 'excels'), 'project_table.xlsx')
    las_file3 = os.path.join(test_file_dir, "Well F.las")
    log_table = LogTable({
        'P velocity': ['Vp_dry', 'Vp_Sg08'],
        'Porosity': ['PHIE'],
        'Volume': ['VSH']
    })
    rule1 = CutoffRule('vp_dry', '>', Q_(3000, 'm/s'))
    rule2 = CutoffRule('phie', '<', Q_(0.1, ''))
    rule3 = CutoffRule('vsh', '>', Q_(0.4, ''))
    well = Well()
    well.read_las(las_file3, log_table=log_table, template_file=project_table)
    return well, Cutoffs([rule1, rule2, rule3])


class TestCases(unittest.TestCase):
    def test_log_plotter1(self):
        lp = LogPlotter()
        print(lp.width)
        lp.width = 600
        print(lp.width)
        self.assertTrue(lp.width == 600)

    def test_line(self):
        cds, line1, line2, line3, wis, cutoffs = make_test_data()
        p1 = figure(title="Line example", x_axis_label="var_one", y_axis_label="md")
        p1.line(x=line1.x, y=line1.y, source=line1.cds, **line1.line_args)
        self.assertIsInstance(line1, Line)

        cds2 = ColumnDataSource(dict(deepcopy(cds.data)))
        cds2.data[line1.x][line1.cds.data[line1.x] > 10.1] = np.nan
        cds2.data[line1.y][line1.cds.data[line1.x] > 10.1] = np.nan
        p2 = figure(title="Masked line example", x_axis_label="x", y_axis_label="y")
        p2.line(x=line1.x, y=line1.y, source=cds2, **line1.line_args)

        show(row(p1, p2))

    def test_column_with_lines(self):
        _, line1, line2, line3, _, _ = make_test_data()
        c1 = LogColumn('c1', lines=[line1, line2, line3])

        p = create_column_figure(c1, None, None, 300, 600, True, True, True, None)
        show(p)
        # print(inspect.getmembers(p.children[0].y_range))
        self.assertTrue(True)

    def test_two_column_plot(self):
        _, line1, line2, line3, _, _ = make_test_data()
        lp = LogPlotter(width=800, height=1000)
        c2 = LogColumn('c2', lines=[line1, line2])
        c1 = LogColumn('c1', lines=[line1, line2, line3], rel_width=2)
        lp.columns = [c2, c1]
        show(lp.draw())
        self.assertTrue(True)

    def test_cutoffs(self, unit_test=True):
        common_cds, line1, line2, line3, _, cutoffs = make_test_data()
        lp = LogPlotter(width=800, height=1000)
        c2 = LogColumn('c2', lines=[line2])
        c1 = LogColumn('c1', lines=[line2, line3], rel_width=2)
        lp.columns = [c2, c1]
        print(common_cds.data.keys())
        grid = lp.draw()
        table, table_buttons, apply_mask, reset_mask = lp.add_cutoffs_table(
            common_cds=common_cds, cutoffs=cutoffs)
        if unit_test:
            show(
                row(
                    grid, column(
                        table,
                        row(table_buttons, apply_mask, reset_mask)
                    )
                )
            )
        else:
            return grid, table, table_buttons, apply_mask, reset_mask

    def test_add_settings(self):
        _, line1, line2, line3, _, _ = make_test_data()
        lp = LogPlotter(width=800, height=1000)
        c2 = LogColumn('c2', lines=[line1, line2])
        c1 = LogColumn('c1', lines=[line1, line2, line3], rel_width=2)
        lp.columns = [c2, c1]
        grid = lp.draw()
        settings = lp.add_settings(grid)
        show(row(grid, settings))

    def test_two_column_plot_with_seismic(self):
        _, line1, line2, line3, _, _ = make_test_data()
        # Synthetic AVO traces spanning the same md range as the test lines
        seismic1 = SeismicTraces(y=np.linspace(1000., 2000., test_data_length))
        lp = LogPlotter(width=800, height=1000)
        c2 = LogColumn('c2', lines=[line1, line2])
        c1 = LogColumn('c1', seismic_traces=seismic1, rel_width=2)
        lp.columns = [c2, c1]
        show(lp.draw())
        self.assertTrue(True)

    def test_link_table(self):
        _, line1, line2, line3, wis, _ = make_test_data()
        lp = LogPlotter(width=800, height=1000)
        c3 = LogColumn('c3', rel_width=0.5)
        c2 = LogColumn('c2', lines=[line1, line2])
        c1 = LogColumn('c1', lines=[line2, line3, line1], rel_width=2)
        lp.columns = [c2, c3, c1]
        p = lp.draw()

        print(p.children)

        data_table = add_strat_table(
            p,
            {'name': ['Viking GP', 'Draupne FM', 'Another FM'],
             'top': [1000., 1400., 1630.], 'base': [2600., 1630., 1900.], 'color': ['red', 'blue', 'green'],
             'level': [0, 1, 1]},
            width=800,
            column_index=1
        )
        show(column(p, data_table))
        self.assertTrue(True)

    def test_well_plotter(self):
        well, cutoffs = make_well_data()
        column_content = [['vsh'], ['phie'], ['vp_dry', 'vp_sg08']]
        well_plot = WellPlotter(well, column_content)
        show(well_plot.draw())

    def test_well_plotter_with_cutoffs(self, unit_test=True):
        well, cutoffs = make_well_data()
        column_content = [['vsh'], ['phie'], ['vp_dry', 'vp_sg08']]
        well_plot = WellPlotter(well, column_content)
        table, table_buttons, apply_mask, reset_mask = well_plot.add_cutoffs_table(cutoffs)
        grid = well_plot.draw()
        if unit_test:
            show(
                row(
                    grid, column(
                        table,
                        row(table_buttons, apply_mask, reset_mask)
                    )
                )
            )
            return None
        else:
            return grid, table, table_buttons, apply_mask, reset_mask

    def test_well_plotter_with_settings(self):
        well, cutoffs = make_well_data()
        column_content = [['vsh'], ['phie'], ['vp_dry', 'vp_sg08']]
        well_plot = WellPlotter(well, column_content)
        grid = well_plot.draw()
        settings_table = well_plot.add_settings(grid)
        show(row(grid, settings_table))
