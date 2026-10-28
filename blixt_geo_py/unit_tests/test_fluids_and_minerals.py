import os
import unittest

import numpy as np

from blixt_geo_py import Q_
from blixt_geo_py.core.core import Cutoffs
from blixt_geo_py.core.fluids_and_minerals import (FluidSpec, InterpolatedFluid, MineralSpec, MixtureComponent,
                                                   SubstitutionCase, VolumeFraction, component_from_row,
                                                   load_fluid_specs, load_mineral_specs, load_substitution_cases,
                                                   make_logs_lowercase, read_sheet_table, resolve_volume_fractions,
                                                   validate_component_set)

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))


class TestCases(unittest.TestCase):
    def test_lowercase(self):
        a = {'A':1, 'B':2}
        print(a)
        make_logs_lowercase(a)
        print(a)

    def test_print_fluid_spec(self):
        fs = FluidSpec(
            name='AnyThing',
            calculation_method='user specified',
            bulk_gpa=30,
            shear_gpa=16,
            density_gcc=3
        )
        print(fs)

    def test_load_fluid_spec(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        for _key, _value in list(load_fluid_specs(project_table).items()):
            for _fluid in ['brine', 'oil', 'gas']:
                info_txt = _value.calc_elastics(_fluid, Q_(3000., 'm'))
                print(info_txt, _key, _fluid , _value)

    def test_load_mineral_spec(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        for _key, _value in list(load_mineral_specs(project_table).items()):
            print(_key, _value)

    def test_read_sheet_table(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        mix = read_sheet_table(project_table, 'Fluid mixtures',
                               {'Use', 'Substitution order',
                                'Well name', 'Interval name',
                                'Fluid name', 'Fluid type', 'Volume fraction'})
        # The following code line should only keep the lines in the table which have "Use == Yes"
        mix = mix[mix['Use'].astype(str).str.strip().str.lower().eq('yes')].copy()
        print(mix)


    def test_component_from_row(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')

        # First test the case with fluids
        fluids = load_fluid_specs(project_table)
        mix = read_sheet_table(project_table, 'Fluid mixtures',
                               {'Use', 'Substitution order',
                                'Well name', 'Interval name',
                                'Fluid name', 'Fluid type', 'Volume fraction'})
        # The following code line should only keep the lines in the table which have "Use == Yes"
        mix = mix[mix['Use'].astype(str).str.strip().str.lower().eq('yes')].copy()
        group_cols = ['Well name', 'Interval name', 'Tag']
        for key, g in mix.groupby(group_cols, dropna=False, sort=False):
            initial = [component_from_row(r, fluids) for _, r in g[g['Substitution order'].eq('Initial')].iterrows()]
            final = [component_from_row(r, fluids) for _, r in g[g['Substitution order'].eq('Final')].iterrows()]
            print('Initial:\n', '\n'.join([str(_i) for _i in initial]))
            print('Final:\n', '\n'.join([str(_f) for _f in final]))

        # Next, try loading the mineral components
        minerals = load_mineral_specs(project_table)
        mix = read_sheet_table(project_table, 'Mineral mixtures',
                               {'Use',
                                'Well name', 'Interval name',
                                'Mineral name', 'Volume fraction'})
        mix = mix[mix['Use'].astype(str).str.strip().str.lower().eq('yes')].copy()
        group_cols = ['Well name', 'Interval name']
        for key, g in mix.groupby(group_cols, dropna=False, sort=False):
            _minerals = [component_from_row(r, minerals) for _, r in g.iterrows()]
            print('Minerals:\n', '\n'.join([str(_i) for _i in _minerals]))

    def test_validate_component_set(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        fluids = load_fluid_specs(project_table)
        mix = read_sheet_table(project_table, 'Fluid mixtures',
                               {'Use', 'Substitution order',
                                'Well name', 'Interval name',
                                'Fluid name', 'Fluid type', 'Volume fraction'})
        # The following code line should only keep the lines in the table which have "Use == Yes"
        mix = mix[mix['Use'].astype(str).str.strip().str.lower().eq('yes')].copy()
        group_cols = ['Well name', 'Interval name', 'Tag']
        for key, g in mix.groupby(group_cols, dropna=False, sort=False):
            initial = [component_from_row(r, fluids) for _, r in g[g['Substitution order'].eq('Initial')].iterrows()]
            final = [component_from_row(r, fluids) for _, r in g[g['Substitution order'].eq('Final')].iterrows()]
            print('Initial is valid?:\n', validate_component_set(initial, 'TEST'))
            print('Final is valid?:\n', validate_component_set(final, 'TEST FINAL'))

        # Next, try loading the mineral components
        minerals = load_mineral_specs(project_table)
        mix = read_sheet_table(project_table, 'Mineral mixtures',
                               {'Use',
                                'Well name', 'Interval name',
                                'Mineral name', 'Volume fraction'})
        mix = mix[mix['Use'].astype(str).str.strip().str.lower().eq('yes')].copy()
        group_cols = ['Well name', 'Interval name']
        for key, g in mix.groupby(group_cols, dropna=False, sort=False):
            _minerals = [component_from_row(r, minerals) for _, r in g.iterrows()]
            print('Minerals are valid:\n', validate_component_set(_minerals, 'TEST MINERAL'))


    def test_load_substitution_cases(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        # First the fluids
        cases = load_substitution_cases(project_table, from_fluid_mixture=True)
        for c in cases:
            print(f'{c.well} | {c.interval} | tag={c.tag}')
            print('  Initial:', [(x.mother_name, x.type, x.volume.mode, x.volume.value) for x in c.initial])
            print('  Final:  ', [(x.mother_name, x.type, x.volume.mode, x.volume.value) for x in c.final])

        # Then the minerals
        cases = load_substitution_cases(project_table, from_fluid_mixture=False)
        for c in cases:
            print(f'{c.well} | {c.interval} | tag={c.tag}')
            print('  Initial:', [(x.mother_name, x.type, x.volume.mode, x.volume.value) for x in c.initial])
            print('  Final:  ', [(x.mother_name, x.type, x.volume.mode, x.volume.value) for x in c.final])

    def test_resolve_volume_fraction(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        n = 10

        # First for fluids
        cases = load_substitution_cases(project_table)
        for c in cases:
            print(f'{c.well} | {c.interval} | tag={c.tag}')
            _out = resolve_volume_fractions(c.initial, {'SW': np.full(n, 0.33)}, n)
            print('  Initial: ', _out)
            _out = resolve_volume_fractions(c.final, {'SW': np.full(n, 0.33)}, n)
            print('  Final: ', _out)

        # Then for minerals
        # And in this case, the initial and final results will be the same
        cases = load_substitution_cases(project_table, from_fluid_mixture=False)
        for c in cases:
            print(f'{c.well} | {c.interval} | tag={c.tag}')
            _out = resolve_volume_fractions(c.initial, {'VCL': np.full(n, 0.33)}, n)
            print('  Initial: ', _out)
            _out = resolve_volume_fractions(c.final, {'VCL': np.full(n, 0.33)}, n)
            print('  Final: ', _out)

    def test_calc_elastics_for_substitution_cases(self):
        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')
        n = 10
        logs = {
            'vp': np.linspace(2900., 3100, n),
            'vs': np.linspace(1400., 1600, n),
            'rho': np.linspace(2.3, 2.5, n),
            'VCL': np.linspace(1., 0.6, n),
            'PHIE': np.linspace(0., 0.2, n),
            'SW': np.linspace(0.05, 1., n)
        }

        # First for fluids
        cases = load_substitution_cases(project_table)
        print('FLUIDS')
        for c in cases:
            print(f'{c.well} | {c.interval} | tag={c.tag}')
            _str = c.calc_elastics(logs, Q_(3000., 'meter'), verbose=True)
            print(_str)

        # Then for minerals
        cases = load_substitution_cases(project_table, from_fluid_mixture=False)
        print('\nMINERALS')
        for c in cases:
            print(f'{c.well} | {c.interval} | tag={c.tag}')
            _str = c.calc_elastics(logs, Q_(3000., 'meter'), verbose=True)
            print(_str)

    def test_calc_elastics_for_substitution_cases_detailed(self):
        fluid_params = {'Bulk moduli [GPa]': None, 'Shear moduli [GPa]': None, 'Density [g/cm3]': None,
                        'Calculation method': 'Batzle and Wang',
                        'T gradient [deg C/m]': 0.03, 'T ref [C]': 5.0,
                        'P gradient [MPa/m]': 0.0107, 'P ref [MPa]': 0.0,
                        'Salinity [ppm]': 70000.0, 'GOR': 1.0, 'Oil API': 30.0,
                        'Gas gravity': 0.6, 'Gas mixing': 'Brie', 'Brie exponent': 2.0}
        fs = FluidSpec(
            name='MyFluid',
            calculation_method='batzle and wang',
            params=fluid_params
        )
        mc1 = MixtureComponent(
            mother_name='MyFluid',
            type='brine',
            volume=VolumeFraction(
                mode='constant',
                value=1,
                excel_value=1
            ),
            source=fs
        )
        mc2 = MixtureComponent(
            mother_name='MyFluid',
            type='brine',
            volume=VolumeFraction(
                mode='log',
                value='SW',
                excel_value='SW'
            ),
            source=fs
        )
        mc3 = MixtureComponent(
            mother_name='MyFluid',
            type='gas',
            volume=VolumeFraction(
                mode='complement',
                value=None,
                excel_value='complement'
            ),
            source=fs
        )
        sc = SubstitutionCase(
            well='Well 1',
            interval='Cook FM',
            tag='GAS',
            initial=[mc1],
            final=[mc2, mc3]
        )

        info_txt = fs.calc_elastics('brine', Q_(2000., 'm'))
        brine_bulk = fs.bulk_gpa
        brine_density = fs.density_gcc

        info_txt = fs.calc_elastics('gas', Q_(2000., 'm'))
        gas_bulk = fs.bulk_gpa
        gas_density = fs.density_gcc

        # The water saturation goes from 0 to 1
        info_txt = sc.calc_elastics({'SW': np.linspace(0.05, 1., 10)}, Q_(2000., 'm'), verbose=False)

        # print(brine_bulk, brine_density)
        # print(gas_bulk, gas_density)
        # print(sc.final_bulk_gpa)
        # print(sc.final_density_gcc)

        # The last sample of the VRH averaged value of the final bulk should equal the brine bulk moduli
        self.assertAlmostEqual(sc.final_bulk_gpa[-1], brine_bulk)

        # The last sample of the VRH averaged value of the final density should equal the brine density
        self.assertAlmostEqual(sc.final_density_gcc[-1], brine_density)

        # The first sample of the VRH averaged value of the final bulk should equal the gas bulk moduli
        self.assertAlmostEqual(sc.final_bulk_gpa[0], gas_bulk)

        # The first sample of the VRH averaged value of the final density should equal the gas density
        self.assertAlmostEqual(sc.final_density_gcc[0], gas_density)

    def test_calc_elastics_for_mineral_detailed(self):
        cutoffs = Cutoffs(from_string='VCL>0.8[], PHIE<0.1[]')
        ms = MineralSpec(
            name='MyMineral',
            calculation_method='interval average',
            cutoffs=cutoffs
        )
        n=20
        logs = {
            'vp': np.linspace(2900., 3100, n),
            'vs': np.linspace(1400., 1600, n),
            'rho': np.linspace(2.3, 2.5, n),
            'VCL': np.linspace(1., 0.6, n),
            'PHIE': np.linspace(0., 0.2, n),
            'SW': np.linspace(0.05, 1., n)
        }
        info_txt = ms.calc_elastics(logs)
        print(ms)

        # if we shift the order of data in VCL and PHIE, we should get a higher result, as the mask
        # then should filter out the lower values of vp, vs, and rho
        logs['VCL'] = np.linspace(0.6, 1, 20)
        logs['PHIE'] = np.linspace(0.2, 0., 20)
        info_txt = ms.calc_elastics(logs)
        print(ms)

    def test_interpolated_fluid(self):
        pvt_table = dict(
            pressure = Q_([10., 15., 20., 25., 30., 35., 40., 45., 50.], 'MPa'),
            rho = Q_([0.12, 0.18, 0.25, 0.31, 0.38, 0.45, 0.52, 0.58, 0.64], 'g/cc'),
            k = Q_([0.020, 0.035, 0.055, 0.080, 0.110, 0.145, 0.185, 0.230, 0.28], 'GPa')
        )

        eos_fluid = InterpolatedFluid(**pvt_table)

        for p in [Q_(_p, 'Pa') for _p in [12.5E+6, 15.E+6, 17.5E+6, 60.E+6]]:
            print(p, eos_fluid.rho(p), eos_fluid.k(p))
