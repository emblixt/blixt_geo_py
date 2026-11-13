import unittest

from blixt_geo_py.core.project import Project


class ProjectTestCase(unittest.TestCase):

    def test_create_project(self):
        wp = Project(name='MyProject',   # uses the new project table
                     log_to_stdout=False)
        with self.subTest():
            print(type(wp))
            self.assertTrue(isinstance(wp, Project))

    def test_load_wells(self):
        from blixt_geo_py.core.core import LogTable
        log_table = LogTable({'Density': 'rho_dry', 'P velocity': 'vp_dry', 'S velocity': 'vs_dry',
                              'Porosity': 'PHIE', 'Volume': 'VCL'})
        for _log_table in (None, log_table):
            wp = Project(name='MyProject', log_to_stdout=True)
            # if _log_table is None:
            #     print('- No LogTable')
            # else:
            #     print('- With LogTable')
            wp.load_all_wells(log_table=_log_table)
            for _w in wp.wells:
                # print('-', _w.name, '\n', _w.header, '\n', _w.style)
                print('-', _w.name, _log_table)
                print(_w.calc_press_ref(None))
                print(_w.header.water_depth)
                _w.create_tvd_ml_log()
                print(_w.get_log_names)
                # for _l in _w.logs:
                #     if _l.style is None:
                #         style_txt = 'STYLE IS LACKING'
                #     else:
                #         style_txt = 'True: {} '.format(_l.style.units)
                #     print('  - log name: {}, unit: {}, depth units: {}, evenly spaced? {}, len: {}, style? {}'.format(_l.name,
                #            _l.units, _l.depth_units, _l.is_evenly_spaced, len(_l), style_txt ))
            self.assertTrue(True)

    def test_selected_wells_are_loaded(self):
        """
        Read the project table directly, independently of the project code, to find which wells should be loaded,
        and compare that with the wells actually loaded by load_all_wells().
        A well should be loaded if it is set to "Use" == "Yes" in the 'Well settings' sheet, AND at least one of its
        files is set to "Use this file" == "Yes" in the 'Well logs' sheet.
        A selected well without any las file in use should not be loaded, and a warning should be raised
        """
        import pandas as pd
        import warnings

        def _is_yes(_val):
            return isinstance(_val, str) and _val.strip().lower() == 'yes'

        def _clean(_name):
            return _name.replace('/', '_').replace('-', '_').replace(' ', '').upper()

        wp = Project(name='MyProject', log_to_stdout=False)
        sheets = pd.read_excel(wp.project_table, header=1, sheet_name=None, engine='openpyxl')

        selected_wells = {_clean(_name) for _name, _use in
                          zip(sheets['Well settings']['Given well name'], sheets['Well settings']['Use'])
                          if isinstance(_name, str) and _is_yes(_use)}
        table = sheets['Well logs']
        wells_with_files = {_clean(_name) for _name, _use in
                            zip(table['Given well name'], table['Use this file'])
                            if isinstance(_name, str) and _is_yes(_use)}
        expected_wells = selected_wells & wells_with_files
        skipped_wells = selected_wells - wells_with_files
        print('Using project table:', wp.project_table)
        print('Wells selected in "Well settings":', sorted(selected_wells))
        print('Wells with las files in use:', sorted(wells_with_files))
        print('Wells expected to be loaded:', sorted(expected_wells))
        print('Wells expected to be skipped, with a warning:', sorted(skipped_wells))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            wp.load_all_wells()
        loaded_wells = {_clean(_w.name) for _w in wp.wells} if wp.wells is not None else set()
        print('Wells loaded:', sorted(loaded_wells))

        self.assertSetEqual(expected_wells, loaded_wells)
        warned_txt = [str(_w.message) for _w in caught if issubclass(_w.category, UserWarning)]
        for _well in skipped_wells:
            self.assertTrue(any(_well in _txt for _txt in warned_txt),
                            'No warning raised for skipped well {}'.format(_well))

    def test_load_selected_wells(self):
        """
        Load wells by name with load_wells(), which ignores the "Use" column of the 'Well settings' sheet.
        Assumes that Well_A has a las file in use in the 'Well logs' sheet, and that Well_F has not
        """
        import warnings

        # (well names given to load_wells(), expected loaded wells, wells expected to be warned about)
        # Loaded well names are cleaned by fix_well_name(), i.e. in upper case
        cases = [
            # A single well name given as a string. Well_A is loaded although "Use" is "No" in 'Well settings'
            ('Well_A', {'WELL_A'}, set()),
            # The well name is matched regardless of upper or lower case
            ('well_a', {'WELL_A'}, set()),
            # A list of well names. Well_A is loaded, while Well_F has no las file in use, so it is skipped with a
            # warning, without stopping the loading of Well_A
            (['Well_A', 'Well_F'], {'WELL_A'}, {'WELL_F'}),
            # Well_F alone: its data in the 'Well data' sheet is in use, but that is not enough, as no las file
            # is in use in the 'Well logs' sheet. So nothing is loaded
            ('Well_F', set(), {'WELL_F'}),
            # A well that does not exist in the project table. Nothing is loaded
            ('No_such_well', set(), {'NO_SUCH_WELL'}),
        ]
        for well_names, expected_wells, warned_wells in cases:
            with self.subTest(well_names=well_names):
                # Start with a fresh project for each case, so that no wells are left from the previous case
                wp = Project(name='MyProject', log_to_stdout=False)

                # Record the warnings. 'always' makes sure a warning is caught every time, and not only the first
                # time it is raised from the same line of code
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter('always')
                    wp.load_wells(well_names)

                # Exactly the expected wells must be loaded, no more and no less
                loaded_wells = {_w.name for _w in wp.wells}
                print('Asked for: {}, loaded: {}'.format(well_names, sorted(loaded_wells)))
                self.assertSetEqual(expected_wells, loaded_wells)

                # Every skipped well must be mentioned in a warning, and a loaded well must not be
                warned_txt = [str(_w.message) for _w in caught if issubclass(_w.category, UserWarning)]
                for _well in warned_wells:
                    self.assertTrue(any(_well in _txt for _txt in warned_txt),
                                    'No warning raised for well {}'.format(_well))
                for _well in expected_wells:
                    self.assertFalse(any(_well in _txt for _txt in warned_txt),
                                     'Unexpected warning raised for loaded well {}'.format(_well))

        # Anything else than a string, or a non-empty list of strings, must raise a TypeError
        with self.subTest(well_names='wrong type'):
            wp = Project(name='MyProject', log_to_stdout=False)
            for bad_names in (None, [], ['Well_A', 1]):
                with self.assertRaises(TypeError):
                    wp.load_wells(bad_names)

    def test_results_folder(self):
        """
        The results folder defaults to <working_dir>/results_folder. A relative path is taken relative to the working
        directory, and the folder is created if it does not exist
        """
        import os
        import tempfile
        from blixt_geo_py.utils.utils import arrange_logging

        # The default results folder, in the default working directory
        wp = Project(name='MyProject', log_to_stdout=True)
        self.assertEqual(os.path.join(wp.working_dir, 'results_folder'), wp.results_folder)
        self.assertTrue(os.path.isdir(wp.results_folder))

        # Use a temporary working directory, so that the created folders are removed afterward.
        # The default project table is not in the temporary folder, so it must be given with its full path
        project_table = wp.project_table
        with tempfile.TemporaryDirectory() as tmp_dir:
            # A relative results folder is created inside the working directory
            wp = Project(name='TmpProject', working_dir=tmp_dir, project_table=project_table,
                         results_folder='my_results', log_to_stdout=True)
            self.assertEqual(os.path.join(tmp_dir, 'my_results'), wp.results_folder)
            self.assertTrue(os.path.isdir(wp.results_folder))

            # An absolute results folder is used as it is, and missing parent folders are created too
            nested_folder = os.path.join(tmp_dir, 'some', 'nested', 'results')
            wp = Project(name='TmpProject', working_dir=tmp_dir, project_table=project_table,
                         results_folder=nested_folder, log_to_stdout=True)
            self.assertEqual(nested_folder, wp.results_folder)
            self.assertTrue(os.path.isdir(nested_folder))

            # A results folder that already exists is kept, together with its content
            existing_file = os.path.join(nested_folder, 'old_result.txt')
            with open(existing_file, 'w') as f:
                f.write('keep me')
            Project(name='TmpProject', working_dir=tmp_dir, project_table=project_table,
                    results_folder=nested_folder, log_to_stdout=True)
            self.assertTrue(os.path.isfile(existing_file))

            # A results folder that is an existing file is not accepted
            with self.assertRaises(NotADirectoryError):
                Project(name='TmpProject', working_dir=tmp_dir, project_table=project_table,
                        results_folder=existing_file, log_to_stdout=True)
            # Release any log file in the temporary folder, so that it can be removed
            arrange_logging(True, None)

    def test_load_from_logfile(self):
        """
        A project set up earlier can be restored from its log file, including the results folder
        """
        import os
        import tempfile
        from blixt_geo_py.utils.utils import arrange_logging

        project_table = Project(name='MyProject', log_to_stdout=True).project_table
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Set up a project that logs to the file <tmp_dir>/TmpProject_log.txt
            wp = Project(name='TmpProject', working_dir=tmp_dir, project_table=project_table,
                         results_folder='my_results', log_to_stdout=False)
            self.assertTrue(os.path.isfile(wp.logging_file))

            # Restore the project from its log file, and check that the settings are the same
            restored = Project(load_from=wp.logging_file)
            for _key in ('name', 'working_dir', 'project_table', 'results_folder', 'logging_file'):
                self.assertEqual(getattr(wp, _key), getattr(restored, _key), _key)
            # Settings that were never set are restored as None, and not as the string 'None'
            self.assertIsNone(restored.tops_file)
            self.assertIsNone(restored.tops_type)
            # The restored project must be usable, e.g. have an empty list of wells
            self.assertEqual(0, len(restored))
            # Release the log file in the temporary folder, so that it can be removed
            arrange_logging(True, None)

    def test_invalid_input(self):
        """
        Wrong input to Project raises an error, instead of silently using something else
        """
        # Neither a name, nor a project table
        with self.assertRaises(ValueError):
            Project(log_to_stdout=True)
        # A working directory that does not exist. Earlier, the default working directory was silently used
        with self.assertRaises(NotADirectoryError):
            Project(name='MyProject', working_dir='C:/no/such/folder', log_to_stdout=True)
        # A project table that does not exist
        with self.assertRaises(FileNotFoundError):
            Project(name='MyProject', project_table='no_such_table.xlsx', log_to_stdout=True)
        # A log file that does not exist
        with self.assertRaises(FileNotFoundError):
            Project(load_from='no_such_log.txt', log_to_stdout=True)
        # An unknown option for what to do when a well exists from before
        with self.assertRaises(ValueError):
            Project(name='MyProject', log_to_stdout=True).add_well(None, if_well_exists='unknown')

    def test_well_log_table(self):
        """
        The well log table lists every log of every loaded well, with the well information (color, symbol, content,
        KB and water depth) taken from the 'Well settings' sheet of the project table. The project table is read
        directly, independently of the project code, to find the expected well information.
        Assumes that Well_A has a las file in use in the 'Well logs' sheet, and has a KB and a water depth in the
        'Well settings' sheet
        """
        import numpy as np
        import pandas as pd
        from bokeh.models import DataTable

        well_columns = ['Color', 'Symbol', 'Content', 'KB', 'Water depth']
        wp = Project(name='MyProject', log_to_stdout=False)
        wp.load_wells('Well_A')
        self.assertTrue(len(wp) > 0, 'No wells loaded, so the well log table can not be tested')

        settings = pd.read_excel(wp.project_table, header=1, sheet_name='Well settings', engine='openpyxl')
        expected_info = {}
        for _, _row in settings.iterrows():
            _name = _row['Given well name']
            if isinstance(_name, str) and _name.upper().strip() not in expected_info:
                expected_info[_name.upper().strip()] = {
                    _col: (None if pd.isna(_row[_col]) else _row[_col]) for _col in well_columns + ['Note']}

        def _value(_v):
            return None if pd.isna(_v) else _v

        with self.subTest('DataFrame'):
            df = wp.well_log_table()
            self.assertListEqual(['Well'] + well_columns + ['Log', 'Log type', 'Units', 'Top', 'Base', 'Samples',
                                                            'Depth type', 'Depth units'], list(df.columns))
            # One row per log, and every log of every well is listed with its log type
            self.assertEqual(sum(len(_w.logs) for _w in wp.wells), len(df))
            for _w in wp.wells:
                _rows = df[df['Well'] == _w.name]
                self.assertDictEqual({_l.name: _l.log_type for _l in _w.logs},
                                     dict(zip(_rows['Log'], _rows['Log type'])))
                # The well information is taken from the project table, and repeated on every row of the well
                for _col in well_columns:
                    for _v in _rows[_col]:
                        self.assertEqual(expected_info[_w.name.upper().strip()][_col], _value(_v), _col)
                # The top is above the base, in the depth units of the log
                self.assertTrue(all(_rows['Top'] <= _rows['Base']))
                # Only the valid data points of each log are counted, i.e. not NaN or infinite values
                self.assertDictEqual({_l.name: int(np.sum(~np.isnan(_l.data.magnitude) & ~np.isinf(_l.data.magnitude)))
                                      for _l in _w.logs},
                                     dict(zip(_rows['Log'], _rows['Samples'])))
                for _l, _n in zip(_rows['Log'], _rows['Samples']):
                    self.assertLessEqual(_n, len(_w.get_log_curve(_l)))
            self.assertTrue(pd.api.types.is_integer_dtype(df['Samples']))
            # Well_A has a KB and a water depth, so these must be filled in
            _rows = df[df['Well'].str.upper() == 'WELL_A']
            self.assertFalse(_rows['KB'].isna().any())
            self.assertFalse(_rows['Water depth'].isna().any())

        with self.subTest('Other well columns'):
            # Any column of the 'Well settings' sheet can be chosen
            df_note = wp.well_log_table(well_columns=['Note'])
            self.assertListEqual(['Well', 'Note'], list(df_note.columns[:2]))
            for _name, _v in zip(df_note['Well'], df_note['Note']):
                self.assertEqual(expected_info[_name.upper().strip()]['Note'], _value(_v))
            # No well columns at all
            self.assertEqual('Log', wp.well_log_table(well_columns=[]).columns[1])
            # A column that does not exist in the 'Well settings' sheet raises an error
            with self.assertRaises(ValueError):
                wp.well_log_table(well_columns=['No such column'])

        with self.subTest('Selected wells'):
            # Well names are matched regardless of upper or lower case
            name = wp.wells[0].name
            self.assertSetEqual({name}, set(wp.well_log_table(name.lower())['Well']))
            # A well that is not loaded gives an empty table
            self.assertEqual(0, len(wp.well_log_table('No_such_well')))

        with self.subTest('Well without logs'):
            # A well without logs is listed on one row, without log information
            from blixt_geo_py.core.well import Well
            empty_well = Well()
            empty_well.name = 'EMPTY_WELL'
            wp.add_well(empty_well)
            _rows = wp.well_log_table('EMPTY_WELL')
            self.assertEqual(1, len(_rows))
            self.assertTrue(pd.isna(_rows['Log'].iloc[0]))
            self.assertTrue(pd.isna(_rows['Samples'].iloc[0]))
            # The empty cells must not break the text, or the Bokeh table, where the json serialization is tested
            self.assertIn('EMPTY_WELL', wp.print_well_log_table())
            from bokeh.embed import json_item
            json_item(wp.bokeh_well_log_table(show_table=False))
            wp.wells.remove(empty_well)

        with self.subTest('Text'):
            txt = wp.print_well_log_table()
            for _w in wp.wells:
                # The well name is only written on the first line of each well
                self.assertEqual(1, txt.count(_w.name))
                for _l in _w.logs:
                    self.assertIn(_l.name, txt)
            for _col in well_columns:
                self.assertIn(_col, txt)
            self.assertIn('Samples', txt)
            # The depth columns can be left out, but the samples column is kept
            txt = wp.print_well_log_table(show_depths=False)
            self.assertNotIn('Depth type', txt)
            self.assertIn('Samples', txt)

        with self.subTest('Bokeh'):
            table = wp.bokeh_well_log_table(show_table=False)
            self.assertIsInstance(table, DataTable)
            self.assertEqual(len(df), len(table.source.data['Well']))
            self.assertListEqual(list(df.columns), [_c.field for _c in table.columns])
            # Without a Color column, there is no color sample
            table = wp.bokeh_well_log_table(show_table=False, well_columns=['KB'])
            self.assertNotIn('Color_hex', table.source.data)
            table = wp.bokeh_well_log_table(show_table=False)
            # The colors are converted to hex for the color sample in the table
            for _color, _hex in zip(table.source.data['Color'], table.source.data['Color_hex']):
                if _color:
                    self.assertTrue(_hex is None or _hex.startswith('#'))

        with self.subTest('Logs not in all wells'):
            import copy
            from blixt_geo_py.core.well import Well
            # With only one well loaded, every log appears in all wells
            self.assertFalse(Project.logs_not_in_all_wells(wp.well_log_table()).any())
            self.assertNotIn('*', wp.print_well_log_table())
            self.assertFalse(any(wp.bokeh_well_log_table(show_table=False).source.data['Log_missing']))

            # Add a second well that only has a copy of the first log of the first well, with the log name in upper
            # case, as log names are compared regardless of case. Then all the other logs of the first well are
            # missing in the second well
            first_well = wp.wells[0]
            shared_log = copy.deepcopy(first_well.logs[0])
            shared_log.name = shared_log.name.upper()
            other_well = Well(logs=[shared_log])
            other_well.name = 'OTHER_WELL'
            wp.add_well(other_well)
            # A well without logs is not considered, otherwise every log would be missing in it
            empty_well = Well()
            empty_well.name = 'EMPTY_WELL'
            wp.add_well(empty_well)

            df = wp.well_log_table()
            missing = Project.logs_not_in_all_wells(df)
            expected = {(first_well.name, _l.name): _l.name.lower() != shared_log.name.lower()
                        for _l in first_well.logs}
            expected[('OTHER_WELL', shared_log.name)] = False
            self.assertDictEqual(expected, {(_w, _l): bool(_m) for _w, _l, _m in zip(df['Well'], df['Log'], missing)
                                            if _w != 'EMPTY_WELL'})
            self.assertFalse(missing[df['Well'] == 'EMPTY_WELL'].any())

            # In the text, the missing logs are marked with a '*', and explained below the table
            txt = wp.print_well_log_table()
            for (_w, _l), _m in expected.items():
                self.assertEqual(_m, '{}*'.format(_l) in txt, _l)
            self.assertIn('* Log does not appear in all wells', txt)

            # In the Bokeh table, the Log cells of the missing logs get a light red background
            from blixt_geo_py.core.project import MISSING_LOG_COLOR
            table = wp.bokeh_well_log_table(show_table=False)
            self.assertListEqual(missing.tolist(), table.source.data['Log_missing'])
            log_column = [_c for _c in table.columns if _c.field == 'Log'][0]
            self.assertIn(MISSING_LOG_COLOR, log_column.formatter.template)
            wp.wells.remove(other_well)
            wp.wells.remove(empty_well)

    def test_load_wells_with_rename(self):
        """
        Set only Well A active in the project table (_new), because it has a rename in it
        :return:
        """
        from blixt_geo_py.core.core import LogTable
        log_table = LogTable({'Gamma ray': ['GR'], 'Resistivity': ['RDEP', 'RMED']})
        wp = Project(name='MyProject', log_to_stdout=True)
        wp.load_all_wells(log_table=log_table)
        for _w in wp.wells:
            for _l in _w.logs:
                if _l.style is None:
                    style_txt = 'STYLE IS LACKING'
                else:
                    style_txt = 'True: {} '.format(_l.style.units)
                print(
                    '  - log name: {}, unit: {}, depth units: {}, evenly spaced? {}, len: {}, style? {}'.format(
                        _l.name, _l.units, _l.depth_units, _l.is_evenly_spaced, len(_l), style_txt))
        self.assertTrue(True)


