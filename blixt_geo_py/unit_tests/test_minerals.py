import os
import unittest

from blixt_geo_py.core.minerals import Mineral, MineralMix, MineralsTable

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))


def make_project():
    from blixt_geo_py.core.project import Project
    project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
    project = Project(name='MyProject', project_table=project_table)
    project.load_all_wells()
    wis = project.load_all_wis()
    return project, wis


class TestCases(unittest.TestCase):
    def test_mineral(self):
        m = Mineral()
        m.from_default('shale')
        print(m)

        print(m.vp())

    def test_read_mineral_mixes(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        my_mineral_mix = MineralMix()
        my_mineral_mix.read_excel(project_table)
        print(my_mineral_mix)
        print(my_mineral_mix.print_all_minerals())

    def test_calc_elastics(self):
        from blixt_geo_py.core.core import LogTable
        project, wis = make_project()
        log_table = LogTable({
            'P velocity': 'vp_dry',
            'S velocity': 'vs_dry',
            'Density': 'rho_dry',
            'Porosity': 'phie',
            'Volume': 'vcl'
        } )
        my_mineral_mix = MineralMix()
        my_mineral_mix.read_excel(project.project_table)
        my_mineral_mix.calc_elastics(project.wells, log_table, wis, debug=True)

    def test_mineral_table(self, unit_test=True):
        ft = MineralsTable(default_minerals_only=True)
        cds = ft.cds
        table, add_row, delete_row, update = ft.draw(cds)
        if unit_test:
            from bokeh.io import output_file
            from bokeh.plotting import show, row, column
            output_file(os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))
            show(column(table, row(add_row, delete_row, update)))
            return None, None, None, None
        else:
            return table, add_row, delete_row, update
