# -*- coding: utf-8 -*-
"""
Module for handling a Project, consisting of many wells
"""
import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd

from blixt_geo_py.core.well import Well
from blixt_geo_py.core.core import LogTable

import blixt_geo_py.io.io as uio
from blixt_geo_py.utils.utils import arrange_logging, print_info

logger = logging.getLogger(__name__)

# Project attributes that are written to the log file when they are set, with the text used in the log file.
# load_logfile() uses the same texts to restore the project settings from the log file
LOGGED_ATTRIBUTES = {
    'name': 'Project name',
    'working_dir': 'Working directory',
    'project_table': 'Project table',
    'results_folder': 'Results folder',
    'tops_file': 'Tops are taken from',
    'tops_type': 'Tops are of type',
}

IF_WELL_EXISTS_OPTIONS = ('append', 'overwrite', 'ask', 'ignore')

# Default columns of the 'Well settings' sheet in the project table that are shown in the well log table
WELL_TABLE_COLUMNS = ('Color', 'Symbol', 'Content', 'KB', 'Water depth')
# Light red background of the Log cells, in the Bokeh well log table, for logs that do not appear in all wells
MISSING_LOG_COLOR = '#f8d7da'


class Project(object):
    def __init__(self,
                 load_from=None,
                 name=None,
                 wells: list | None = None,
                 working_dir=None,
                 project_table=None,
                 results_folder=None,
                 log_to_stdout=False,
                 ):
        """
        class that keeps central information about the current well project in memory.

        :param load_from:
            str
            full pathname of existing log file from previously set up project.
            The other input parameters, except log_to_stdout, are ignored
        :param name:
            str
            Name of the project
        :param wells:
            list
            List of Well objects
        :param working_dir:
            str
            folder name of the project.
            Default is the folder that contains the blixt_geo_py package
        :param project_table:
            str
            full pathname of .xlsx file that store information of which wells and logs, ... to use.
            A relative path is taken relative to the working directory.
            Default is <working_dir>/excels/project_table.xlsx
        :param results_folder:
            str
            folder where the results are saved. It is created if it does not exist.
            A relative path is taken relative to the working directory.
            Default is <working_dir>/results_folder
        :param log_to_stdout:
            bool
            If True, the logging information is sent to standard output and not to file
        """
        self.wells = [] if wells is None else wells
        self.templates = None

        if load_from is not None:
            self.load_logfile(load_from, log_to_stdout=log_to_stdout)
            return

        if name is None:
            if project_table is not None:
                name = os.path.splitext(os.path.basename(project_table))[0]
            else:
                error_txt = 'Either the name, or the project table, must be provided'
                print_info(error_txt, 'error', logger)
                raise ValueError(error_txt)

        if working_dir is None:
            # The folder that contains the blixt_geo_py package
            working_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
        elif not os.path.isdir(working_dir):
            error_txt = 'The provided working directory {}, does not exist'.format(working_dir)
            print_info(error_txt, 'error', logger)
            raise NotADirectoryError(error_txt)

        self.logging_file = os.path.join(working_dir, '{}_log.txt'.format(name))
        arrange_logging(log_to_stdout, self.logging_file, logging.INFO)

        print_info('Project created / modified on: {}'.format(datetime.now().isoformat()), 'info', logger)
        self.name = name
        self.working_dir = working_dir
        self.tops_file = None
        self.tops_type = None

        if project_table is None:
            project_table = os.path.join(self.working_dir, 'excels', 'project_table.xlsx')
        elif not os.path.isfile(project_table):
            project_table = os.path.join(self.working_dir, project_table)
        if not os.path.isfile(project_table):
            error_txt = 'The provided project table {}, does not exist'.format(project_table)
            print_info(error_txt, 'error', logger)
            raise FileNotFoundError(error_txt)
        self.project_table = project_table

        self.set_results_folder(results_folder)

    def __setattr__(self, key, value):
        """
        Catch changing attributes in the log file
        :param key:
        :param value:
        :return:
        """
        if key in LOGGED_ATTRIBUTES:
            print_info('{}: {}'.format(LOGGED_ATTRIBUTES[key], value), 'info', logger)

        super(Project, self).__setattr__(key, value)

    def __str__(self):
        keys = list(self.__dict__.keys())

        pattern = "%%%ds: %%s" % max(len(k) for k in keys)

        head = [pattern % (k, self.__dict__[k]) for k in keys]
        return "\n".join(head)

    def __len__(self):
        return len(self.wells)

    def set_results_folder(self, results_folder: str | None = None):
        """
        Sets the folder where the results are saved, and creates it if it does not exist

        :param results_folder:
            str
            A relative path is taken relative to the working directory.
            Default is <working_dir>/results_folder
        """
        if results_folder is None:
            results_folder = os.path.join(self.working_dir, 'results_folder')
        elif not os.path.isabs(results_folder):
            results_folder = os.path.join(self.working_dir, results_folder)
        if os.path.exists(results_folder) and not os.path.isdir(results_folder):
            error_txt = 'The results folder {}, is a file and not a folder'.format(results_folder)
            print_info(error_txt, 'error', logger)
            raise NotADirectoryError(error_txt)
        if not os.path.isdir(results_folder):
            os.makedirs(results_folder)
            print_info('Created the results folder: {}'.format(results_folder), 'info', logger)
        self.results_folder = results_folder

    @property
    def get_well_names(self):
        return [_well.name for _well in self.wells]

    def get_well(self, name: str):
        for _well in self.wells:
            if _well.name.lower() == name.lower():
                return _well
        return None

    def add_well(self, well: Well, if_well_exists: str = 'append', if_log_exists: str = 'overwrite'):
        """
        Adds a Well object to the Project
        :param well:
        :param if_well_exists:
            str
            Describes what to do if the well exists from before. Well names are compared regardless of upper or
            lower case
            'append': Append the logs of the new well to the old well
            'overwrite': Overwrite old well
            'ask': Ask to overwrite or ignore
            'ignore': new well is ignored if a well of same name exists from before
        :param if_log_exists:
            str
            Describes what to do if the log exists from before
            'overwrite': Overwrite old log
            'ask': Ask to overwrite or ignore
            'ignore': new log is ignored if a log of same name exists from before
        :return:
        """
        if if_well_exists not in IF_WELL_EXISTS_OPTIONS:
            raise ValueError("Unknown value ({}) of 'if_well_exists'. Must be one of {}".format(
                if_well_exists, ', '.join(IF_WELL_EXISTS_OPTIONS)))
        if self.wells is None:
            self.wells = []

        well_name_list = [_name.lower() for _name in self.get_well_names]
        if well.name.lower() not in well_name_list:
            self.wells.append(well)
            return

        _index = well_name_list.index(well.name.lower())
        if if_well_exists == 'append':
            if well.logs is None:
                return
            for _log in well.logs:
                self.wells[_index].add_log(_log, if_log_exists=if_log_exists)
            if well.header.note is not None:
                if self.wells[_index].header.note is None:
                    self.wells[_index].header.note = well.header.note
                else:
                    self.wells[_index].header.note += well.header.note
            self.wells[_index].header.modification_history += "\nAppended logs: {}, using '{}'".format(
                ', '.join([_l.name for _l in well.logs]), if_log_exists)
        elif if_well_exists == 'overwrite':
            self.wells[_index] = well
        elif if_well_exists == 'ask':
            response = input('Well ({}) exists! Overwrite? ["No"]:'.format(well.name)) or "No"
            if response != "No":
                self.wells[_index] = well

    def load_logfile(self, file_name, log_to_stdout: bool = False):
        """
        Restores the project settings from the log file of a previously set up project.
        When the same setting is found several times in the log file, the last one is used

        :param file_name:
            str
            full pathname of the log file
        :param log_to_stdout:
            bool
            If True, the logging information is sent to standard output and not to the log file
        """
        if not os.path.isfile(file_name):
            error_txt = 'The provided log file {}, does not exist'.format(file_name)
            print_info(error_txt, 'error', logger)
            raise FileNotFoundError(error_txt)

        with open(file_name, 'r') as f:
            lines = f.readlines()

        settings = {_key: None for _key in LOGGED_ATTRIBUTES}
        for line in lines:
            for _key, _text in LOGGED_ATTRIBUTES.items():
                if '{}: '.format(_text) in line:
                    _value = line.split('{}: '.format(_text), 1)[1].strip()
                    settings[_key] = None if _value == 'None' else _value  # unset values are logged as 'None'

        for _key in ('name', 'working_dir', 'project_table'):
            if settings[_key] is None:
                error_txt = "The log file {} does not contain the '{}' of the project".format(
                    file_name, LOGGED_ATTRIBUTES[_key])
                print_info(error_txt, 'error', logger)
                raise ValueError(error_txt)

        # Continue logging to the same log file, so that the restored settings are logged to it
        self.logging_file = file_name
        arrange_logging(log_to_stdout, file_name, logging.INFO)

        self.name = settings['name']
        self.working_dir = settings['working_dir']
        self.project_table = settings['project_table']
        self.tops_file = settings['tops_file']
        self.tops_type = settings['tops_type']
        # Log files from before the results folder was introduced get the default results folder
        self.set_results_folder(settings['results_folder'])

        print_info('Loaded project settings from: {}'.format(file_name), 'info', logger)

    def load_all_wells(self, if_well_exists: str = 'append', if_log_exists: str = 'overwrite',
                       log_table: LogTable | None = None, verbose: bool = False):
        """
        Load all logs and well data that are listed in the project table where "Use" == "Yes"
        See _load_wells() for the parameters
        """
        self._load_wells(None, if_well_exists=if_well_exists, if_log_exists=if_log_exists,
                         log_table=log_table, verbose=verbose)

    def load_wells(self, well_names: str | list[str], if_well_exists: str = 'append',
                   if_log_exists: str = 'overwrite', log_table: LogTable | None = None, verbose: bool = False):
        """
        Load the logs and well data of the given wells, ignoring the "Use" column of the 'Well settings' sheet in
        the project table. Only files with "Use this file" == "Yes" are loaded.
        See _load_wells() for the other parameters

        :param well_names:
            str or list of str
            Name(s) of the well(s) to load, as given in the "Given well name" column of the project table
        """
        if isinstance(well_names, str):
            well_names = [well_names]
        if not (isinstance(well_names, list) and len(well_names) > 0 and
                all(isinstance(_name, str) for _name in well_names)):
            raise TypeError('well_names must be a string, or a non-empty list of strings, not {}'.format(well_names))
        self._load_wells(well_names, if_well_exists=if_well_exists, if_log_exists=if_log_exists,
                         log_table=log_table, verbose=verbose)

    def _load_wells(self, well_names: list[str] | None, if_well_exists: str = 'append',
                    if_log_exists: str = 'overwrite', log_table: LogTable | None = None, verbose: bool = False):
        """
        Load logs and well data that are listed in the project table
        :param self:
        :param well_names:
            list of str
            Names of the wells to load.
            If None, the wells set to "Use" == "Yes" in the 'Well settings' sheet of the project table are loaded
        :param if_well_exists:
            str
            Describes what to do if the well exists from before
            'append': Append the logs of the new well to the old well
            'overwrite': Overwrite old well
            'ask': Ask to overwrite or ignore
            'ignore': new well is ignored if a well of same name exists from before
        :param if_log_exists:
            str
            Describes what to do if the log exists from before
            'overwrite': Overwrite old log
            'ask': Ask to overwrite or ignore
            'ignore': new log is ignored if a log of same name exists from before
        :param log_table:
            LogTable
            If provided only the logs in LogTable will be loaded
        :param verbose:
            bool
            If True, the files that are read are printed to standard output. They are always logged
        :return:
        """
        result = uio.project_wells_new(self.project_table, self.working_dir, do_rename=True,
                                       selected_wells=well_names)

        for _key in list(result.keys()):  # _key is the name of the file to read
            print_info('Reading from file {}'.format(_key), 'info', logger, verbose=verbose)
            translate_dict = None
            if 'Translate log names' in list(result[_key].keys()) and result[_key]['Translate log names'] is not None:
                translate_dict = uio.interpret_rename_string(result[_key]['Translate log names'])
                print_info('Translating log names: {}'.format(translate_dict), 'info', logger, verbose=verbose)
            w = Well()
            if uio.filetype(_key) == 'las':
                if log_table is None:
                    # Create a LogTable based on the logs listed in 'result'
                    _log_table = LogTable()
                    _log_table.from_invert(result[_key]['logs'])
                else:
                    _log_table = log_table.keep(list(result[_key]['logs'].keys()))

                # Force name of well to be that given in the project_table, and not given by the las file
                w.name = result[_key]['Given well name']
                w.header.name = result[_key]['Given well name']

                w.read_las(_key, log_table=_log_table, template_file=self.project_table, rename_logs=translate_dict,
                           verbose=verbose)

            elif uio.filetype(_key) in ['txt', 'dat', 'ascii', 'asc', 'dev', 'cs']:
                var_names = list(result[_key]['logs'].keys())
                var_columns = [result[_key]['columns'][_var] for _var in var_names]
                var_units = [result[_key]['units'][_var] for _var in var_names]
                var_types = [result[_key]['logs'][_var] for _var in var_names]
                # The well name must be set before reading, so that the well settings in the project table are found
                w.name = result[_key]['Given well name']
                w.header.name = result[_key]['Given well name']
                w.read_general_ascii(
                    file_name=_key,
                    separator=result[_key]['Separator'],
                    data_begins_on_row=result[_key]['Data begins on line'],
                    var_names=var_names,
                    var_columns=var_columns,
                    var_units=var_units,
                    var_types=var_types,
                    encoding=None,
                    template_file=self.project_table,
                )
                w.header.note = result[_key]['Note']
            else:
                print_info('File {} is of unknown format. Skipped'.format(_key), 'warning', logger)

            if w.logs is not None:
                self.add_well(w, if_well_exists=if_well_exists, if_log_exists=if_log_exists)

        self.load_all_templates()

    def load_all_templates(self):
        from blixt_geo_py.core.core import Template, templates_from_table
        if self.project_table is None:
            return
        _templates = {}
        with pd.ExcelFile(self.project_table) as xl:
            for sheet_name, well_style in (('Templates', False), ('Well settings', True)):
                table = pd.read_excel(xl, sheet_name=sheet_name, header=1)
                template_dict = templates_from_table(table, well_style=well_style)
                for _key in list(template_dict.keys()):
                    _templates[_key] = Template.from_dict(template_dict[_key])
        self.templates = _templates

    def load_all_wis(self):
        from blixt_geo_py.core.core import Intervals
        wis = Intervals()
        if self.project_table is not None:
            wis.read_blixt_tops(self.project_table)
        return wis

    def well_settings(self, well_columns: list[str] | tuple[str, ...] = WELL_TABLE_COLUMNS) -> dict:
        """
        Reads the 'Well settings' sheet of the project table

        :param well_columns:
            list of str
            Columns of the 'Well settings' sheet to read
        :return:
            dict
            {well name: {column: value}}, where the well names are cleaned by fix_well_name(), and empty cells are None.
            If a well is listed several times, the first row is used
        """
        from blixt_geo_py.utils.utils import fix_well_name
        table = pd.read_excel(self.project_table, header=1, sheet_name='Well settings', engine='openpyxl')
        missing = [_col for _col in well_columns if _col not in table.columns]
        if missing:
            raise ValueError("Column(s) {} not found in the 'Well settings' sheet of {}. Available columns: {}".format(
                ', '.join(missing), self.project_table, ', '.join(str(_c) for _c in table.columns)))
        settings = {}
        for _, _row in table.iterrows():
            _name = fix_well_name(_row['Given well name'])
            if _name is None or _name in settings:
                continue
            settings[_name] = {_col: (None if pd.isna(_row[_col]) else _row[_col]) for _col in well_columns}
        return settings

    def well_log_table(self, wells: str | list[str] | None = None,
                       well_columns: list[str] | tuple[str, ...] = WELL_TABLE_COLUMNS) -> pd.DataFrame:
        """
        Returns a table with one row per log, listing the well, the well information taken from the
        'Well settings' sheet of the project table (color, symbol, content, KB, water depth by default), and the log
        name, log type, units and depth range of each log.

        :param wells:
            str or list of str
            Name(s) of the wells to include. Default is all wells loaded in the project
        :param well_columns:
            list of str
            Columns of the 'Well settings' sheet that are added to the table, e.g. also 'Discovery in' or 'Note'
        :return:
            pandas.DataFrame
            with columns: Well, <well_columns>, Log, Log type, Units, Top, Base, Samples, Depth type, Depth units
            where Samples is the number of valid (not NaN or infinite) data points of the log
        """
        from blixt_geo_py.utils.utils import fix_well_name
        well_columns = list(well_columns)
        log_columns = ['Log', 'Log type', 'Units', 'Top', 'Base', 'Samples', 'Depth type', 'Depth units']
        if isinstance(wells, str):
            wells = [wells]
        settings = self.well_settings(well_columns)

        rows = []
        for _well in self.wells:
            if wells is not None and _well.name.lower() not in [_w.lower() for _w in wells]:
                continue
            _settings = settings.get(fix_well_name(_well.name), {})
            _well_part = [_well.name] + [_settings.get(_col) for _col in well_columns]
            if not _well.logs:
                rows.append(_well_part + [None] * len(log_columns))
                continue
            for _log in _well.logs:
                try:
                    _top, _base = _log.depth.top.magnitude, _log.depth.base.magnitude
                except (IndexError, AttributeError):
                    _top, _base = None, None
                try:
                    # Only valid data points are counted, i.e. not NaN or infinite values
                    _samples = int(np.count_nonzero(np.isfinite(np.asarray(_log.values, dtype=float))))
                except (TypeError, ValueError):
                    _samples = None
                rows.append(_well_part + [_log.name, _log.log_type, str(_log.units), _top, _base, _samples,
                                          _log.depth_type, str(_log.depth_units)])
        df = pd.DataFrame(rows, columns=['Well'] + well_columns + log_columns)
        # Integers that allow empty cells, for wells without logs
        df['Samples'] = df['Samples'].astype('Int64')
        return df

    @staticmethod
    def logs_not_in_all_wells(df: pd.DataFrame) -> pd.Series:
        """
        Finds the logs of a well log table (see well_log_table()) whose log name does not appear in all wells of the
        table. Log names are compared regardless of upper or lower case.
        Wells without logs are not considered, as they would otherwise make every log missing in some well

        :param df:
            pandas.DataFrame
            Well log table, as returned by well_log_table()
        :return:
            pandas.Series of bool
            True for the rows whose log is missing in at least one of the other wells
        """
        has_log = df['Log'].notna()
        log_names = df['Log'].where(has_log, '').astype(str).str.lower()
        n_wells = df.loc[has_log, 'Well'].nunique()
        n_wells_per_log = df[has_log].groupby(log_names[has_log])['Well'].nunique()
        return has_log & (log_names.map(n_wells_per_log) < n_wells)

    def print_well_log_table(self, wells: str | list[str] | None = None, show_depths: bool = True,
                             well_columns: list[str] | tuple[str, ...] = WELL_TABLE_COLUMNS) -> str:
        """
        Prints, and returns, the well log table (see well_log_table()) as text, where the well name and the well
        information are only written on the first line of each well.
        Logs that do not appear in all wells are marked with a '*'

        :param wells:
            str or list of str
            Name(s) of the wells to include. Default is all wells loaded in the project
        :param show_depths:
            bool
            If False, the depth type, top, base and depth units columns are left out. The samples column is kept
        :param well_columns:
            list of str
            Columns of the 'Well settings' sheet that are added to the table
        :return:
            str
        """
        df = self.well_log_table(wells, well_columns=well_columns)
        missing = self.logs_not_in_all_wells(df)
        if not show_depths:
            df = df.drop(columns=['Depth type', 'Top', 'Base', 'Depth units'])
        df = df.astype(object).where(df.notna(), '')
        df.loc[missing, 'Log'] = df.loc[missing, 'Log'] + '*'
        repeated = df['Well'].eq(df['Well'].shift())
        df.loc[repeated, ['Well'] + list(well_columns)] = ''
        txt = df.to_string(index=False, float_format=lambda _x: '{:.1f}'.format(_x))
        if missing.any():
            txt += '\n* Log does not appear in all wells'
        print(txt)
        return txt

    def bokeh_well_log_table(self, wells: str | list[str] | None = None, show_table: bool = True,
                             file_name: str | None = None, width: int = 1200, height: int | None = None,
                             well_columns: list[str] | tuple[str, ...] = WELL_TABLE_COLUMNS):
        """
        Creates a Bokeh DataTable of the well log table (see well_log_table()), where the Color column shows a
        sample of the well color, and the Log cells of logs that do not appear in all wells are colored light red

        :param wells:
            str or list of str
            Name(s) of the wells to include. Default is all wells loaded in the project
        :param show_table:
            bool
            If True, the table is shown (in the browser, or in the notebook if bokeh.io.output_notebook() is used)
        :param file_name:
            str
            Name of the html file the table is saved to when shown. A relative path is taken relative to the
            results folder. Default is <results_folder>/<project name>_well_log_table.html
        :param width:
            int
            Width of the table in pixels
        :param height:
            int
            Height of the table in pixels. Default fits all rows, up to 800 pixels
        :param well_columns:
            list of str
            Columns of the 'Well settings' sheet that are added to the table
        :return:
            bokeh.models.DataTable
        """
        from bokeh.models import ColumnDataSource, DataTable, TableColumn, HTMLTemplateFormatter, NumberFormatter
        from bokeh.io import output_file, show
        from matplotlib.colors import to_hex

        df = self.well_log_table(wells, well_columns=well_columns)
        table_columns = list(df.columns)
        missing = self.logs_not_in_all_wells(df)

        def _to_hex(_c):
            try:
                return to_hex(_c)
            except (ValueError, TypeError):
                return None

        has_color = 'Color' in df.columns
        if has_color:
            df['Color_hex'] = [_to_hex(_c) for _c in df['Color']]
        # Numeric columns keep NaN for empty cells, so that Bokeh can format them, while text columns get ''
        numeric = [_col for _col in df.columns if pd.api.types.is_numeric_dtype(df[_col])]
        for _col in df.columns:
            if _col in numeric:
                # pd.NA in integer columns, like Samples, can not be serialized by Bokeh
                df[_col] = df[_col].astype(float)
            else:
                df[_col] = [('' if (_v is None or (isinstance(_v, float) and pd.isna(_v))) else _v)
                            for _v in df[_col]]
        # Added after the conversion above, so that it stays bool
        df['Log_missing'] = missing.tolist()

        color_formatter = HTMLTemplateFormatter(template=(
            '<% if (Color_hex) { %>'
            '<span style="display:inline-block;width:12px;height:12px;margin-right:4px;vertical-align:middle;'
            'border:1px solid #888;background:<%= Color_hex %>"></span><% } %><%= value %>'))
        # Light red background of the cell for logs that do not appear in all wells
        log_formatter = HTMLTemplateFormatter(template=(
            '<div style="background:<%= Log_missing ? \'' + MISSING_LOG_COLOR + '\' : \'transparent\' %>;'
            'margin:0 -4px;padding:0 4px;height:100%"><%= value %></div>'))
        # A dict, and not the DataFrame, avoids a pandas deprecation warning from Bokeh
        source = ColumnDataSource(data={_col: df[_col].tolist() for _col in df.columns})
        columns = []
        for _col in table_columns:
            if _col == 'Color' and has_color:
                columns.append(TableColumn(field=_col, title=_col, formatter=color_formatter))
            elif _col == 'Log':
                columns.append(TableColumn(field=_col, title=_col, formatter=log_formatter))
            elif _col in numeric:
                _format = '0' if _col == 'Samples' else '0.0'
                columns.append(TableColumn(field=_col, title=_col, formatter=NumberFormatter(format=_format)))
            else:
                columns.append(TableColumn(field=_col, title=_col))

        if height is None:
            height = min(800, 30 + 25 * max(len(df), 1))
        table = DataTable(source=source, columns=columns, width=width, height=height, index_position=None)

        if show_table:
            if file_name is None:
                file_name = '{}_well_log_table.html'.format(self.name)
            if not os.path.isabs(file_name):
                file_name = os.path.join(self.results_folder, file_name)
            output_file(file_name, title='{}: wells and logs'.format(self.name))
            show(table)
        return table

    def dict(self, wells: list | None = None, intervals: list | None = None, logs: list | None = None):
        """
        Returns a dictionary where the data is sorted in wells -> working intervals -> logs
        eg:
            {'well A':
                {'interval 1':
                    {'log A': LogCurve2dNew,
                    'log B': LogCurve2dNew,
                    ...},
                'interval 2':
                    {'log B': LogCurve2dNew,
                    'log C': LogCurve2dNew,
                    ...},
                ...},
            'well B':
                {
                ...}
            ...}


        :return:
        """
        raise NotImplementedError('Project.dict() is not implemented yet')
