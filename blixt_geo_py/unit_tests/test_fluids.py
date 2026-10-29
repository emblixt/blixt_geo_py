from copy import deepcopy
import os
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
import blixt_geo_py.unit_tests.plot_settings  # noqa: F401

import blixt_geo_py.rp.rp_core as rp
from blixt_geo_py import Q_
from blixt_geo_py.core.core import Intervals
from blixt_geo_py.core.fluids import (FluidMix, FluidsTable, MotherFluid, def_fluid_vals,
                                      read_all_mother_fluids_from_excel, read_fluidmixes_from_excel,
                                      read_fluidmixes_from_excel_test)

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))


def make_fluids():
    project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
    intervals = Intervals(name='MyIntervals')
    intervals.read_blixt_tops(project_table)

    myfluids = read_fluidmixes_from_excel(project_table, intervals)
    all_mother_fluids = read_all_mother_fluids_from_excel(project_table)
    return all_mother_fluids, myfluids


class TestCases(unittest.TestCase):
    def test_read_fluid_mixes(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        intervals = Intervals(name='MyIntervals')
        intervals.read_blixt_tops(project_table)
        # my_fluid_mixes = read_fluidmixes_from_excel(project_table, intervals)
        my_fluid_mixes = read_fluidmixes_from_excel_test(project_table, intervals)

        # fmix = FluidMix(name='MyFluidMix', fluids=my_fluid_mixes)
        # print(fmix.necessary_logs())
        # print(fmix.print_all_fluids(verbose=False))
        # for _fluid in fmix.get_fluids(
        #     subst_order='fInal',
        #         # subst_order=None,
        #     well_name='wElL_F',
        #     # well_name=None,
        #     wi_name='sand E',
        #     # wi_name=None,
        #     # mother_fluid_name='DEFAULT',
        #     mother_fluid_name=None,
        #     # fluid_type='bRiNe',
        #     fluid_type=None,
        #     # volume_fraction='complement',
        #     volume_fraction=None,
        #     # tag='XX',
        #     tag=None,
        #     verbose=True
        # ):
        #     info_txt = ' Fluid: {}, type: {}, mother fluid: {}, '.format(
        #         _fluid.name, _fluid.fluid_type, _fluid.mother_fluid.name )
        #     print(info_txt)

    def test_calc_elastics(self):
        from blixt_geo_py.core.project import Project

        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        wp = Project(name='MyProject', project_table=project_table)
        wp.load_all_wells()
        wells = {_w.name.lower(): _w for _w in wp.wells}

        intervals = Intervals(name='MyIntervals')
        intervals.read_blixt_tops(project_table)

        fmix = FluidMix(name='Fluids')
        fmix.read_excel(project_table, intervals)
        # print(fmix.print_all_fluids())

        fmix.calc_elastics(wells, True)

        print(fmix.print_all_fluids(verbose=True))

    def test_fluid(self):
        # The defaults describe a MotherFluid; 'status' belongs to a Fluid
        default = {_k: _v for _k, _v in def_fluid_vals.items() if _k != 'status'}
        f1 = MotherFluid(**default)
        print(f1)
        for ft in ['Brine', 'Oil', 'Gas']:
            f1.calc_elastics(ft, Q_(1000., 'm'))
            print('{}: '.format(ft), f1.k, f1.mu, f1.rho)


    def test_fluid_table(self, unit_test=True):

        all_fluids, fluid_mix = make_fluids()
        ft = FluidsTable(mother_fluids=list(all_fluids.values()))
        # ft = FluidsTable(default_fluids_only=True)
        cds = ft.cds
        # for _key in list(cds.data.keys()):
        #     print(_key, cds.data[_key])
        table, add_row, delete_row, update = ft.draw(cds)
        if unit_test:
            from bokeh.io import output_file
            from bokeh.plotting import show, row, column
            output_file(os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))
            show(column(table, row(add_row, delete_row, update)))
            return None, None, None, None
        else:
            return table, add_row, delete_row, update

    def test_fluidsub(self):
        from blixt_geo_py.core.core import LogTable, Cutoffs, CutoffRule
        from blixt_geo_py.core.well import Well
        from blixt_geo_py.core.log_curve import Depth, LogCurve
        from blixt_geo_py.plotting.cross_plotter import CrossPlotter

        file_dir = str(os.path.dirname(__file__).replace(
            'blixt_geo_py\\unit_tests',
            ''))
        project_table = os.path.join(file_dir, 'excels\\project_table.xlsx')

        las_file =  os.path.join(file_dir, 'test_data/Well A.las')
        _output_file = os.path.join(file_dir, 'results_folder/plot.html')

        logs = {'vp_dry': 'P velocity', 'vp_so08': 'P velocity', 'vp_sg08': 'P velocity',
                'vs_dry': 'S velocity', 'vs_so08': 'S velocity', 'vs_sg08': 'S velocity',
                'rho_dry': 'Density', 'rho_so08': 'Density', 'rho_sg08': 'Density',
                'phie': 'Porosity', 'vcl': 'Volume', 'dept': 'MD'}
        lt = LogTable()
        lt.from_invert(logs)

        w1 = Well()
        w1.read_las(las_file, log_table=lt, template_file=project_table)

        # Calculate and apply this mask:
        # w.calc_mask({'vcl': ['<', 0.4], 'phie': ['>', 0.1]}, name='sand')  # calc_mask only works for the old Well
        cr1 = CutoffRule('vcl', '<', Q_(0.4, ''))
        cr2 = CutoffRule('phie', '>', Q_(0.1, ''))
        ct = Cutoffs([cr1, cr2])

        w_dict = w1.dict(cutoffs=ct, use_cutoffs=True)
        # w_dict = w1.dict(cutoffs=ct, use_cutoffs=False)  # Now it creates and an extra parameter 'mask'

        test = 'array'  # 'constants'
        # Test with constant Vsh and constant Sw
        v_sh = 0.2
        s_w = 0.2
        if test == 'array':  # test with arrays of v_sh and s_w
            v_sh = w_dict['vcl'].magnitude
            # create a mock-up water saturation
            s_w = 0.2 + v_sh
            s_w[s_w > 1.0] = 1.0

        # Mineral models, K & MU in GPa, rho in g/cm3
        rho_qz = 2.6;   k_qz = 37;  mu_qz = 44
        rho_sh = 2.8;   k_sh = 15;  mu_sh = 5

        # Mineral shear and bulk modulus using Voigt-Reuss-Hill average for given Vsh
        k0 = rp.vrh_bounds([v_sh, (1.-v_sh)], [k_sh, k_qz])[-1]  # GPa
        mu0 = rp.vrh_bounds([v_sh, (1.-v_sh)], [mu_sh, mu_qz])[-1]  # GPa
        rho0 = v_sh*rho_sh + (1. - v_sh)*rho_qz  # g/cm3

        # Brine model, rho in g/cm3, K in GPa
        rho_b = 1.1;   k_b = 2.8

        # Hydrocarbon model, K in GPa
        fluid = 'oil'
        rho_o = 0.8;    k_o = 0.9
        rho_g = 0.2;    k_g = 0.06
        (k_hc, rho_hc) = (k_g, rho_g) if fluid == 'gas' else (k_o, rho_o)

        # intitial fluid
        rho_f1 = rho_b; k_f1 = k_b

        # After fluid substitution
        rho_f2 = s_w*rho_b + (1.-s_w)*rho_hc
        k_f2 = rp.vrh_bounds([s_w, (1.-s_w)], [k_b, k_hc])[1]  # Reuss uniform fluid mix

        w2 = Well()
        w2.name = 'Fluid Sub'
        v_p_2, v_s_2, rho_2, k_2 = rp.gassmann_vel(
            w_dict['vp_dry'].magnitude,
            w_dict['vs_dry'].magnitude,
            w_dict['rho_dry'].magnitude,
            k_f1, rho_f1, k_f2, rho_f2, k0,
            w_dict['phie'].magnitude)
        # Add fluid subst. logs to well
        depth = Depth(w_dict['dept'])
        lc_vp = LogCurve('vp_so08', Q_(v_p_2, 'm/s'), depth, log_type='P velocity', style=deepcopy(w1.get_log_curve('vp_dry').style))
        w2.add_log(lc_vp)
        lc_vs = LogCurve('vs_so08', Q_(v_s_2, 'm/s'), depth, log_type='S velocity', style=deepcopy(w1.get_log_curve('vs_dry').style))
        w2.add_log(lc_vs)
        lc_rho = LogCurve('rho_so08', Q_(rho_2, 'g/cm**3'), depth, log_type='Density', style=deepcopy(w1.get_log_curve('rho_dry').style))
        w2.add_log(lc_rho)
        lc_depth = LogCurve('dept', Q_(depth.magnitude, depth.units), depth, log_type='MD')
        w2.add_log(lc_depth)


        xp = CrossPlotter({w.name: w.data_source() for w in [w1, w2]})
        cds = xp.cds
        xp.show_plot(cds, out_file=_output_file)
