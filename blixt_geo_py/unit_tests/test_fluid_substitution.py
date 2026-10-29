import os
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
import blixt_geo_py.unit_tests.plot_settings  # noqa: F401

from blixt_geo_py import Q_
from blixt_geo_py.core.core import CutoffRule, Cutoffs, LogTable
from blixt_geo_py.core.project import Project
from blixt_geo_py.analysis.fluid_substitution import run_fluid_substitution

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))


class TestCases(unittest.TestCase):
    def test_fluid_sub(self):
        # Create a project
        wp = Project(
            name='FluidSub',
            project_table=os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx'),
            working_dir=os.path.join(project_dir, 'blixt_geo_py')
        )
        pvt_table = dict(
            pressure = Q_([10., 15., 20., 25., 30., 35., 40., 45., 50.], 'MPa'),
            rho = Q_([0.12, 0.18, 0.25, 0.31, 0.38, 0.45, 0.52, 0.58, 0.64], 'g/cc'),
            k = Q_([0.020, 0.035, 0.055, 0.080, 0.110, 0.145, 0.185, 0.230, 0.28], 'GPa')
        )

        # Load wells (and then automatically all templates)
        wp.load_all_wells(verbose=True)
        wells = {_w.name: _w for _w in wp.wells}
        print(list(wells.keys()))

        # Load working intervals
        wis = wp.load_all_wis()

        # Create cutoffs
        cutoffs = Cutoffs(
            cutoffs=[CutoffRule('Volume', '<', Q_(0.5, '')),
                     CutoffRule('Porosity', '>', Q_(0.1, ''))],
            name='sst'
        )

        # Create log table
        log_table = LogTable({'P velocity': 'vp_dry', 'S velocity': 'vs_dry', 'Density': 'rho_dry',
                              'Porosity': 'phie', 'Volume': 'vcl'})

        # Take into account that the Cutoffs are created using LogTypes and not log names
        cutoffs = cutoffs.use_log_table(log_table)

        # print the names of the important logs prior to fluid substitution:
        print('Original:')
        for _log_type in log_table.log_types:
            for _wn, _w in wells.items():
                print(' {} | {}: {}'.format(_wn, _log_type, ', '.join([_l.name for _l in _w.get_logs_of_type(_log_type)])))

        run_fluid_substitution(
            wells,
            wp.project_table,
            log_table,
            cutoffs,
            wis,
            pvt_table=pvt_table,
            save_result_folder=os.path.join(project_dir, 'blixt_geo_py\\results_folder'),
            result_file_postfix='XXX',
            verbose=True)

        # print the names of the important logs prior to fluid substitution:
        print('Final:')
        for _log_type in log_table.log_types:
            for _wn, _w in wells.items():
                print(' {} | {}: {}'.format(_wn, _log_type, ', '.join([_l.name for _l in _w.get_logs_of_type(_log_type)])))

        for _w in wells.values():
            _file = os.path.join(project_dir, 'blixt_geo_py\\results_folder\\fs_plot_{}.html'.format(_w.name))
            _w.plot([
                ['vp_dry', 'vp_dry_fs_MyTag', 'vp_dry_fs_Cond'],
                ['vs_dry', 'vs_dry_fs_MyTag', 'vs_dry_fs_Cond'],
                ['rho_dry', 'rho_dry_fs_MyTag', 'rho_dry_fs_Cond']],
                _file,
                wis=wis)
