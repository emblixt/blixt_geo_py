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
        files is set to "Use this file" == "Yes" in the 'Well logs' or 'Well data' sheets
        """
        import pandas as pd

        def _is_yes(_val):
            return isinstance(_val, str) and _val.strip().lower() == 'yes'

        def _clean(_name):
            return _name.replace('/', '_').replace('-', '_').replace(' ', '').upper()

        wp = Project(name='MyProject', log_to_stdout=False)
        sheets = pd.read_excel(wp.project_table, header=1, sheet_name=None, engine='openpyxl')

        selected_wells = {_clean(_name) for _name, _use in
                          zip(sheets['Well settings']['Given well name'], sheets['Well settings']['Use'])
                          if isinstance(_name, str) and _is_yes(_use)}
        wells_with_files = set()
        for sheet_name in ('Well logs', 'Well data'):
            if sheet_name not in sheets:
                continue
            table = sheets[sheet_name]
            wells_with_files.update(_clean(_name) for _name, _use in
                                    zip(table['Given well name'], table['Use this file'])
                                    if isinstance(_name, str) and _is_yes(_use))
        expected_wells = selected_wells & wells_with_files
        print('Wells selected in "Well settings":', sorted(selected_wells))
        print('Wells with files in use:', sorted(wells_with_files))
        print('Wells expected to be loaded:', sorted(expected_wells))

        wp.load_all_wells()
        loaded_wells = {_clean(_w.name) for _w in wp.wells} if wp.wells is not None else set()
        print('Wells loaded:', sorted(loaded_wells))

        self.assertSetEqual(expected_wells, loaded_wells)

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


