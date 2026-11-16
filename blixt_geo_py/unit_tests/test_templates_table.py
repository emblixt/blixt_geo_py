import os
import shutil
import tempfile
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
import blixt_geo_py.unit_tests.plot_settings  # noqa: F401

import numpy as np
from bokeh.models import ColumnDataSource, CustomJS
from bokeh.plotting import column, row, show
from openpyxl import load_workbook

from blixt_geo_py.core.templates_table import (ProjectTemplatesTable, MPL_TO_BOKEH_MARKER, bokeh_marker,
                                               log_types_of)

test_file_dir = str(os.path.dirname(__file__).replace(
    'blixt_geo_py\\unit_tests',
    'test_data'))
project_table = os.path.join(test_file_dir.replace('test_data', 'excels'), 'project_table.xlsx')


def all_cells(file_name: str) -> dict:
    """
    Returns {(sheet, row, column): value} of all cells in the workbook
    """
    wb = load_workbook(file_name)
    _out = {}
    for ws in wb.worksheets:
        for _row in ws.iter_rows():
            for _c in _row:
                if _c.value is not None:
                    _out[(ws.title, _c.row, _c.column)] = _c.value
    return _out


def row_of(data: dict, key_column: str, key: str) -> int:
    return list(data[key_column]).index(key)


class TestCases(unittest.TestCase):
    def setUp(self):
        # save() is always tested on a copy of the project table
        self.tmp_dir = tempfile.mkdtemp()
        self.tmp_table = os.path.join(self.tmp_dir, 'project_table.xlsx')
        shutil.copy2(project_table, self.tmp_table)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_cds_content(self):
        table = ProjectTemplatesTable(project_table)
        log_data = table.log_cds.data
        i = row_of(log_data, 'log_type', 'Resistivity')
        self.assertEqual('log', log_data['scale'][i])
        self.assertEqual(0.2, log_data['min'][i])
        self.assertEqual(200., log_data['max'][i])
        self.assertEqual('#1f77b4', log_data['line_color'][i])
        # Missing min and max are NaN, and a missing line style gets the default
        i = row_of(log_data, 'log_type', 'Bulk modulus')
        self.assertTrue(np.isnan(log_data['min'][i]))
        self.assertEqual('-', log_data['line_style'][i])

        well_data = table.well_cds.data
        i = row_of(well_data, 'well', 'Well_B')
        self.assertEqual('#ff7f0e', well_data['color'][i])
        self.assertEqual('s', well_data['symbol'][i])
        # Rows without a well name are not included
        self.assertNotIn(None, well_data['well'])
        # Nothing is edited yet
        self.assertEqual([], table.changes())

    def test_marker_mapping(self):
        wb = load_workbook(project_table, read_only=True)
        symbols = [_r[3] for _r in wb['Well settings'].iter_rows(min_row=3, values_only=True) if _r[3] is not None]
        for _s in symbols:
            self.assertIn(_s, MPL_TO_BOKEH_MARKER)
        self.assertEqual('square', bokeh_marker('s'))
        self.assertEqual('circle', bokeh_marker(None))

    def test_save_only_edited_cells(self):
        before = all_cells(self.tmp_table)
        table = ProjectTemplatesTable(self.tmp_table)
        log_data = table.log_cds.data
        well_data = table.well_cds.data
        log_data['line_color'][row_of(log_data, 'log_type', 'Density')] = '#ff0000'
        log_data['max'][row_of(log_data, 'log_type', 'Density')] = 3.0
        log_data['min'][row_of(log_data, 'log_type', 'Bulk modulus')] = 10.
        well_data['symbol'][row_of(well_data, 'well', 'Well_A')] = 'D'
        self.assertEqual(4, len(table.changes()))

        written = table.save()
        self.assertEqual(4, len(written))
        self.assertTrue(os.path.isfile(table.backup_file))
        self.assertEqual(before, all_cells(table.backup_file))
        # Saving again without new edits writes nothing
        self.assertEqual([], table.changes())
        self.assertEqual([], table.save())

        after = all_cells(self.tmp_table)
        changed = {_k: (before.get(_k), after.get(_k)) for _k in set(before) | set(after)
                   if before.get(_k) != after.get(_k)}
        self.assertEqual(4, len(changed))
        self.assertEqual({'#ff0000', 3, 10, 'D'}, {_v[1] for _v in changed.values()})
        self.assertEqual({'Templates', 'Well settings'}, {_k[0] for _k in changed})

        # The saved settings are read back
        table = ProjectTemplatesTable(self.tmp_table)
        i = row_of(table.log_cds.data, 'log_type', 'Density')
        self.assertEqual('#ff0000', table.log_cds.data['line_color'][i])
        self.assertEqual(3.0, table.log_cds.data['max'][i])
        i = row_of(table.well_cds.data, 'well', 'Well_A')
        self.assertEqual('D', table.well_cds.data['symbol'][i])

    def test_on_save(self):
        calls = []
        table = ProjectTemplatesTable(self.tmp_table, on_save=lambda: calls.append(1))
        table.log_cds.data['line_width'][0] = 3.
        table.save()
        self.assertEqual([1], calls)

    def test_static_dialog(self):
        # Without a Bokeh server: the Save button is inactive, and all links are JavaScript callbacks
        from blixt_geo_py.unit_tests.test_log_plotter import make_well_data
        from blixt_geo_py.plotting.log_plotter import WellPlotter
        from blixt_geo_py.plotting.cross_plotter import CrossPlotter

        table = ProjectTemplatesTable(project_table, allow_save=False)
        button, dialog = table.draw()
        save = [_c for _c in dialog.content.children[-2].children if _c.label.startswith('Save')][0]
        self.assertTrue(save.disabled)
        self.assertEqual(0, len(save._event_callbacks))

        well, cutoffs = make_well_data()
        well_plot = WellPlotter(well, [['vsh'], ['phie'], ['vp_dry', 'vp_sg08']])
        self.assertEqual('P velocity', well_plot.log_types['vp_dry'])
        grid = well_plot.draw(title=well.name)
        well_plot.link_templates(grid, table.log_cds)
        self.assertEqual(2, sum(len(_cbs) for _cbs in table.log_cds.js_property_callbacks.values()))

        ds = well.data_source()
        xp = CrossPlotter({ds.name: ds}, x='vp_dry', y='phie')
        cds = xp.cds
        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = xp.draw(cds)
        style_table = xp.add_data_source_style(cds)
        xp.link_templates(cds, table.log_cds, table.well_cds, log_types=log_types_of(well))
        # The current color and symbol of Well_F are applied to its data source directly
        i = row_of(table.well_cds.data, 'well', 'Well_F')
        color, symbol = table.well_cds.data['color'][i], table.well_cds.data['symbol'][i]
        self.assertEqual([color], list(xp._style_table.cds.data['color']))
        self.assertEqual([bokeh_marker(symbol)], list(xp._style_table.cds.data['marker']))
        self.assertEqual({color}, set(cds.data['color']))
        self.assertTrue(any(isinstance(_cb, CustomJS) for _cb in x_menu.js_property_callbacks['change:value']))

        controls = row(button)
        controls.elements = [dialog]
        show(column(controls, row(grid, column(xplot, row(x_menu, y_menu), style_table))))


if __name__ == '__main__':
    unittest.main()
