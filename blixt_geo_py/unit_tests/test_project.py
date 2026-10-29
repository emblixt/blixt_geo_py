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


