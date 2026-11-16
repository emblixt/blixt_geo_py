# -*- coding: utf-8 -*-
"""
An interactive version of the 'Templates' and 'Well settings' sheets of the project table.

ProjectTemplatesTable holds two ColumnDataSources of plot settings:
    log_cds   - one row per log type, from the 'Templates' sheet
    well_cds  - one row per well, with its color and symbol from the 'Well settings' sheet

The tables are shown in a Bokeh Dialog. Plots are linked to the two sources with
LogPlotter.link_templates() and CrossPlotter.link_templates(), so edits in the dialog update the plots directly.
These links are JavaScript callbacks, and work in a static html page too.
Only the Save button, which writes the edited cells back to the project table, needs a Bokeh server.
"""
import logging
import os
from collections.abc import Callable

import numpy as np
import pandas as pd
from bokeh.models import ColumnDataSource

from blixt_geo_py.io.project_table_writer import normalize, to_cell, backup, write_cells
from blixt_geo_py.utils.utils import print_info

logger = logging.getLogger(__name__)

# The symbols of the 'Well settings' sheet are matplotlib markers. This is the Bokeh marker used for each of them
MPL_TO_BOKEH_MARKER = {
    'o': 'circle',
    's': 'square',
    'v': 'inverted_triangle',
    '^': 'triangle',
    '>': 'triangle',
    '<': 'triangle',
    'D': 'diamond',
    'd': 'diamond',
    'p': 'hex',
    'h': 'hex',
    'H': 'hex',
    '*': 'star',
    '+': 'cross',
    'x': 'x',
    'X': 'x',
    '.': 'dot',
}
DEFAULT_BOKEH_MARKER = 'circle'

# Line styles of the 'Templates' sheet, and their Bokeh line dash
LINE_STYLES = {'-': 'solid', '--': 'dashed', ':': 'dotted', '-.': 'dashdot', '.-': 'dotdash'}
SCALES = ['lin', 'log', 'discrete']

# The editable columns of each source: cds column -> header in the project table
LOG_COLUMNS = {
    'scale': 'scale',
    'min': 'min',
    'max': 'max',
    'line_color': 'line color',
    'line_style': 'line style',
    'line_width': 'line width',
}
WELL_COLUMNS = {
    'color': 'Color',
    'symbol': 'Symbol',
}
# The sheet, the header of the key column, the cds column holding the key and the editable columns of each source
_SHEETS = {
    'log': ('Templates', 'Log type', 'log_type', LOG_COLUMNS),
    'well': ('Well settings', 'Given well name', 'well', WELL_COLUMNS),
}
# The headers are in the second row of the project table sheets, the first row holds notes
_HEADER_ROW = 2
_NUMERIC = ('min', 'max', 'line_width')


def bokeh_marker(symbol) -> str:
    """
    Returns the Bokeh marker of a matplotlib symbol, as used in the 'Well settings' sheet of the project table
    """
    if not isinstance(symbol, str):
        return DEFAULT_BOKEH_MARKER
    return MPL_TO_BOKEH_MARKER.get(symbol.strip(), DEFAULT_BOKEH_MARKER)


# The helpers are shared with the other dialogs that write to the project table
_normalize = normalize
_to_cell = to_cell


class ProjectTemplatesTable:
    def __init__(self,
                 project_table: str,
                 width: int | None = None,
                 allow_save: bool = True,
                 on_save: Callable | None = None):
        """
        Interactive tables of the plot settings in the 'Templates' and 'Well settings' sheets of the project table

        :param project_table:
            str
            Full path name of the project table
        :param width:
            int
            Width of the tables in the dialog
        :param allow_save:
            bool
            When False, the Save button of the dialog is inactive. Use this in a static html page, where there is no
            Bokeh server to run the Python code that writes to the project table
        :param on_save:
            Callable
            Called without arguments after the project table is saved, e.g. Project.load_all_templates
        """
        if not os.path.isfile(project_table):
            raise FileNotFoundError('The project table {} does not exist'.format(project_table))
        self.project_table = project_table
        self.width = 700 if width is None else width
        self.allow_save = allow_save
        self.on_save = on_save
        self.backup_file = None
        self.dialog = None
        self._message = None

        self._log_cds = ColumnDataSource(self._read_log_types())
        self._well_cds = ColumnDataSource(self._read_wells())
        # The values as they are in the project table, which are compared with the edited values when saving
        self._snapshot = {'log': self._values('log'), 'well': self._values('well')}

    @property
    def log_cds(self) -> ColumnDataSource:
        return self._log_cds

    @property
    def well_cds(self) -> ColumnDataSource:
        return self._well_cds

    def _read_log_types(self) -> dict:
        table = pd.read_excel(self.project_table, header=1, sheet_name='Templates', engine='openpyxl')
        _dict = {_key: [] for _key in ['log_type', 'unit'] + list(LOG_COLUMNS)}
        for _i, _log_type in enumerate(table['Log type']):
            if not isinstance(_log_type, str) or _log_type.strip() == '':
                continue
            _dict['log_type'].append(_log_type.strip())
            _dict['unit'].append(_normalize(table['unit'][_i]) or '')
            _dict['scale'].append(_normalize(table['scale'][_i]) or 'lin')
            for _key in ('min', 'max'):
                _value = _normalize(table[_key][_i], numeric=True)
                _dict[_key].append(np.nan if _value is None else _value)
            _dict['line_color'].append(_normalize(table['line color'][_i]) or 'blue')
            _line_style = _normalize(table['line style'][_i])
            _dict['line_style'].append(_line_style if _line_style in LINE_STYLES else '-')
            _line_width = _normalize(table['line width'][_i], numeric=True)
            _dict['line_width'].append(1. if _line_width is None else _line_width)
        for _key in _NUMERIC:
            _dict[_key] = np.array(_dict[_key], dtype=float)
        return _dict

    def _read_wells(self) -> dict:
        table = pd.read_excel(self.project_table, header=1, sheet_name='Well settings', engine='openpyxl')
        _dict = {_key: [] for _key in ['use', 'well'] + list(WELL_COLUMNS)}
        for _i, _well in enumerate(table['Given well name']):
            if not isinstance(_well, str) or _well.strip() == '':
                continue
            _dict['use'].append(_normalize(table['Use'][_i]) or '')
            _dict['well'].append(_well.strip())
            _dict['color'].append(_normalize(table['Color'][_i]) or '#1f77b4')
            _symbol = _normalize(table['Symbol'][_i])
            _dict['symbol'].append(_symbol if _symbol in MPL_TO_BOKEH_MARKER else 'o')
        return _dict

    def _values(self, which: str) -> dict:
        """
        Returns {key: {cds column: normalized value}} of the editable columns of the log or well source
        """
        sheet, key_header, key_column, columns = _SHEETS[which]
        data = self.log_cds.data if which == 'log' else self.well_cds.data
        _out = {}
        for _i, _key in enumerate(data[key_column]):
            _out[_key] = {_c: _normalize(data[_c][_i], numeric=_c in _NUMERIC) for _c in columns}
        return _out

    def changes(self) -> list[tuple]:
        """
        Returns the edited cells as a list of (sheet, key header, key, header, new value), e.g.
            ('Templates', 'Log type', 'Density', 'line color', '#ff0000')
        """
        _out = []
        for which, (sheet, key_header, key_column, columns) in _SHEETS.items():
            current = self._values(which)
            for _key, _values in current.items():
                for _column, _value in _values.items():
                    if self._snapshot[which].get(_key, {}).get(_column) != _value:
                        _out.append((sheet, key_header, _key, columns[_column], _value))
        return _out

    def save(self, file_name: str | None = None) -> list[tuple]:
        """
        Writes the edited cells to the project table. Only the edited cells of the rows with the same log type or
        well name are written, so the rest of the project table is kept as it is.
        The first time it saves, it makes a backup copy of the project table, <name>.bak.xlsx

        :param file_name:
            str
            Full path name of the project table. Default is the project table the settings were read from
        :return:
            list of the cells that were written, see changes()
        """
        from openpyxl import load_workbook
        from blixt_geo_py.io.io import check_if_excelfile_writable

        if file_name is None:
            file_name = self.project_table
        changes = self.changes()
        if len(changes) == 0:
            self._show_message('No changes to save')
            return []

        if self.backup_file is None:
            self.backup_file = backup(file_name)

        if not check_if_excelfile_writable(file_name):
            self._show_message('Could not write to {}. Is it open in Excel?'.format(os.path.basename(file_name)))
            return []

        wb = load_workbook(file_name)
        written = []
        for sheet, key_header, _, _ in _SHEETS.values():
            cells = [(_c[2], _c[3], _c[4]) for _c in changes if _c[0] == sheet]
            written += [(sheet, key_header) + _c for _c in write_cells(wb, sheet, _HEADER_ROW, key_header, cells)]
        wb.save(file_name)

        self._snapshot = {'log': self._values('log'), 'well': self._values('well')}
        for _c in written:
            print_info('{}: {} {}, {} = {}'.format(_c[0], _c[1], _c[2], _c[3], _c[4]), 'info', logger)
        self._show_message('Saved {} cells to {}'.format(len(written), os.path.basename(file_name)))
        if self.on_save is not None:
            self.on_save()
        return written

    def _show_message(self, text: str):
        print_info(text, 'info', logger)
        if self._message is not None:
            self._message.text = text

    def table_columns(self) -> tuple[list, list]:
        from bokeh.models import (SelectEditor, StringEditor, NumberEditor, TableColumn, HTMLTemplateFormatter,
                                  NumberFormatter, CellEditor)

        def colored_cell(field):
            return HTMLTemplateFormatter(template="""
                <div style="background:<%= {} %>; color: white"><%= value %></div>
                """.format(field))

        number = NumberFormatter(format='0[.][000]', nan_format='')
        log_columns = [
            TableColumn(field='log_type', title='Log type', editor=CellEditor(), width=140),
            TableColumn(field='unit', title='Unit', editor=CellEditor(), width=70),
            TableColumn(field='scale', title='Scale', editor=SelectEditor(options=SCALES), width=60),
            TableColumn(field='min', title='Min', editor=NumberEditor(), formatter=number, width=60),
            TableColumn(field='max', title='Max', editor=NumberEditor(), formatter=number, width=60),
            TableColumn(field='line_color', title='Line color', editor=StringEditor(),
                        formatter=colored_cell('line_color'), width=80),
            TableColumn(field='line_style', title='Line style', editor=SelectEditor(options=list(LINE_STYLES)),
                        width=60),
            TableColumn(field='line_width', title='Line width', editor=NumberEditor(step=0.5), formatter=number,
                        width=60),
        ]
        well_columns = [
            TableColumn(field='use', title='Use', editor=CellEditor(), width=40),
            TableColumn(field='well', title='Well', editor=CellEditor(), width=140),
            TableColumn(field='color', title='Color', editor=StringEditor(), formatter=colored_cell('color'),
                        width=80),
            TableColumn(field='symbol', title='Symbol', editor=SelectEditor(options=list(MPL_TO_BOKEH_MARKER)),
                        width=60),
        ]
        return log_columns, well_columns

    def draw(self) -> tuple:
        """
        :return:
            The button that opens the dialog, and the dialog. The dialog must be added to a layout to be available,
            e.g. layout.elements = [dialog], or use widget() which does this
        """
        from bokeh.models import Button, CustomJS, DataTable, Dialog, Div
        from bokeh.plotting import column, row

        def title(text):
            return Div(text='<div style="font-size:12px; font-weight:600">{}</div>'.format(text))

        log_columns, well_columns = self.table_columns()
        log_table = DataTable(source=self.log_cds, columns=log_columns, editable=True, width=self.width,
                              height=400, index_position=None)
        well_table = DataTable(source=self.well_cds, columns=well_columns, editable=True, width=self.width,
                               height=200, index_position=None)

        self._message = Div(text='')
        if self.allow_save:
            save = Button(label='Save to project table', button_type='success')
            save.on_click(lambda: self.save())
        else:
            save = Button(label='Save (needs bokeh serve)', button_type='success', disabled=True)
        close = Button(label='Close')

        self.dialog = Dialog(
            title='Project templates',
            content=column(
                Div(text='Edits are shown in the linked plots directly. {}'.format(
                    'Save writes them to {}'.format(os.path.basename(self.project_table)) if self.allow_save else
                    'They are lost when the page is reloaded')),
                title('Log types'), log_table,
                title('Wells'), well_table,
                row(save, close), self._message),
            visible=False,
            close_action='hide')
        close.js_on_click(CustomJS(args=dict(dialog=self.dialog), code='dialog.visible = false;'))

        button = Button(label='Templates', button_type='success')
        button.js_on_click(CustomJS(args=dict(dialog=self.dialog), code='dialog.visible = true;'))
        return button, self.dialog

    def widget(self):
        """
        Returns a row with the button that opens the dialog, with the dialog attached to it
        """
        from bokeh.plotting import row
        button, dialog = self.draw()
        controls = row(button)
        controls.elements = [dialog]
        return controls


def log_types_of(wells) -> dict:
    """
    Returns {log name: log type} of all logs in the wells, which links the logs in the plots to the log types in
    the templates dialog, see LogPlotter.link_templates() and CrossPlotter.link_templates()

    :param wells:
        Well, or list of Wells, e.g. Project.wells
    """
    if not isinstance(wells, (list, tuple)):
        wells = [wells]
    _out = {}
    for _well in wells:
        for _log in (_well.logs or []):
            if _log.log_type is not None:
                _out[_log.name] = _log.log_type
    return _out
