# -*- coding: utf-8 -*-
"""
Module for handling a Project, consisting of many wells
"""
import logging
import os
from datetime import datetime

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
