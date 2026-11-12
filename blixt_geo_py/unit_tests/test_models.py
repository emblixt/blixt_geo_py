import os
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
from blixt_geo_py.unit_tests.plot_settings import show_or_close

import matplotlib.pyplot as plt
import numpy as np
from bokeh.io import output_file
from pint import DimensionalityError

from blixt_geo_py.core.core import LithoFluids, LithoFluidsTable
from blixt_geo_py.core.seismic import AvoAnalyzer

# Add to path to avoid having to install libraries, useful in development
project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))
output_file(os.path.join(project_dir, 'blixt_geo_py', 'test_data','plot.html'))

from blixt_geo_py.core.models import (Model, Layer, ModelTable, LaminarModel, WedgeModel, FaultModel,
                                  plot_wiggles, build_layered_model, laminar_model_analysis,
                                  build_saturation_wedge, detect_change_in_cases, build_wedge,
                                  layer_names_data)
from blixt_geo_py.core.core import LithoFluid
import blixt_geo_py.core.wavelets as bumw
from blixt_geo_py import Q_

# l1 = {'vp': 3000, 'vs': 1820, 'rho': 2.6}
# l2 = {'vp': 2900, 'vs': 1620, 'rho': 2.2}
l1 = LithoFluid(default='shale')
l2 = LithoFluid(default='brine_sst')
layer1 = Layer('Top', 'Base', thickness=Q_(50., 'm'), litho_fluid=l1)
layer2 = Layer('Reservoir', 'Base', thickness=Q_(20., 'm'), litho_fluid=l2)
layer3 = Layer('Reservoir', 'Oil', thickness=Q_(20., 'm'), litho_fluid=LithoFluid(default='oil_sst'))
layer4 = Layer('Reservoir', 'Gas', thickness=Q_(20., 'm'), litho_fluid=LithoFluid(default='oil_sst'))
layer5 = Layer('Basement', 'Base', thickness=Q_(50., 'm'), litho_fluid=l1)
layer6 = Layer('Basement', 'Oil', thickness=Q_(50., 'm'), litho_fluid=l1)

class TestCase(unittest.TestCase):

    def test_layer(self):
        from copy import deepcopy
        l1 = deepcopy(layer1)
        print(l1.layer_type, l1.thickness)
        def thick(i):
            return Q_(i, 'm')
        l1.thickness = thick
        print(l1.layer_type, l1.thickness, l1.thickness(5))
        i = np.arange(10)
        plt.plot(i, l1.thickness(i).magnitude)
        show_or_close()


    def test_1d(self):
        m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer1, layer2, layer3, layer4, layer5])
        # print(m.layer_names)
        # print(m.case_names)
        print(m.index_of('Reservoir', 'Base'))
        print(m.index_of('Reservoir', 'Oil'))
        print(m.index_of('Basement', 'Oil'))

        print(m.target_layers)
        print(m.base_case_layers)
        print(m.base_target_combos)

    def test_combos(self):
        m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer1, layer2, layer3, layer4, layer5, layer6])
        print(m.base_target_combos)

    def test_failing_models(self):
        # # Model with one layer being repeated
        # m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer1, layer1, layer1])
        # print(m.base_target_combos)

        # # Model with layers that have no name or case
        # layer0 = Layer(thickness=Q_(50., 'm'), litho_fluid=l1)
        # m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer0, layer0, layer0])
        # print(m.base_target_combos)

        # Model with layers that have no name but different cases
        # A target layer (case other than the base case) without a name is invalid
        layer_1 = Layer(case='Base', thickness=Q_(50., 'm'), litho_fluid=l1)
        with self.assertRaises(IOError):
            Layer(case='Oil', thickness=Q_(50., 'm'), litho_fluid=l1)

    def test_depth_range(self):
        m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer1, layer2, layer3, layer4, layer5])
        print(m.total_thickness())
        self.assertTrue(m.total_thickness().magnitude == 120.)

    def test_depth_array(self):
        m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer1, layer2, layer3, layer4, layer5])
        print(m.depth_array(Q_(10., 'm')))

    def test_interface_indexes(self):
        m = Model(depth_to_top=Q_(2000, 'm'), layers=[layer1, layer2, layer3, layer5])
        res = Q_(10., 'm')
        print(m.interface_indexes(res))
        print(m.depth_array(res)[m.interface_indexes(res)])
        test = m.depth_array(res)[m.interface_indexes(res)] == Q_([2050., 2070.], 'm')
        print(test)
        self.assertTrue(all(test))

    def test_1d_twt(self):
        first_layer = Layer(name='A', thickness=Q_(0.1, 's'), litho_fluid=l1)
        second_layer = Layer(name='B', thickness=Q_(0.04, 's'), litho_fluid=l2)
        third_layer = Layer(name='C', thickness=Q_(0.04, 's'), litho_fluid=l2)
        m = Model(depth_to_top=Q_(2.0, 's'), layers=[first_layer, second_layer])
        m.append(third_layer)
        print(m.layer_names)
        m.plot()
        show_or_close()

    def test_1d_z(self):
        first_layer = Layer(thickness=Q_(150, 'm'), litho_fluid=l1)
        second_layer = Layer(thickness=Q_(40, 'm'), litho_fluid=l2)
        m = Model(depth_to_top=Q_(3000., 'm'), layers=[first_layer, second_layer])
        m.append(first_layer)
        m.plot()
        show_or_close()

    def test_wedge_old(self):
        m = build_wedge(Q_(2.0, 's'), Q_(0.02, 's'), Q_(0.1, 's'), 51, l1, l2, l1)
        # m = build_wedge(3000., 10.0, 40., 51, l1, l2, l1, domain='Z')
        m.plot()
        show_or_close()

    def test_plot(self):
        first_layer = Layer(thickness=Q_(0.1, 's'), litho_fluid=l1)
        second_layer = Layer(thickness=Q_(0.04, 's'), litho_fluid=l2, target=True)
        m = Model(depth_to_top=Q_(2.0, 's'), layers=[first_layer, second_layer])
        m.append(first_layer)

        wavelet = bumw.ricker(0.096, 0.001, 25)
        plot_wiggles(m, 0.001, wavelet, avo_angles=[0., 5., 10., 15., 20., 25., 30., 35., 40.])
        plot_wiggles(m, 0.001, wavelet, eei=True, avo_angles=[-90, -70., -50., -30., -15., 0., 15., 30., 50., 70., 90.],
                     extract_avo_at=(-90, 1.99))

    def test_ntg(self):

        thin_bed_factor = 3
        net_vp = 3000.
        resolution = 0.001
        fig, axs = plt.subplots(nrows=11)
        for i in range(11):
            ntg = i / 10.

            ntg_layer = Layer(target=True, thickness=Q_(0.1, 's'), vp=net_vp, ntg=ntg, thin_bed_factor=thin_bed_factor)

            m = Model(layers=[ntg_layer])

            x, _, _ = m.layers[0].realize_layer(resolution)
            net = len(x[x == net_vp])

            print('Requested len: {}, returned len: {}'.format(int(m.layers[0].thickness / resolution), len(x)))
            axs[i].set_title('NTG={}, tbf={}. Observed NTG {:.2f}'.format(ntg, thin_bed_factor, net / len(x)))
            axs[i].plot(x)
        show_or_close()

    def test_realization(self):
        # in TWT
        first_layer = Layer(thickness=Q_(0.1, 's'), vp=3300, vs=1500, rho=2.1)
        second_layer = Layer(thickness=Q_(0.1, 's'), vp=3500, vs=1600, rho=2.3)
        m = Model(layers=[first_layer, second_layer])
        m.append(first_layer)
        m.plot()
        twt, li, vp, _, _, _ = m.realize_model(0.001)
        print(len(vp))
        fig, ax = plt.subplots()
        ax.plot(twt, vp / 1000., twt, li)

        # in Z
        first_layer = Layer(thickness=Q_(100, 'm'), vp=3300, vs=1500, rho=2.1)
        second_layer = Layer(thickness=Q_(20., 'm'), vp=3500, vs=1600, rho=2.3)
        m = Model(layers=[first_layer, second_layer])
        m.append(first_layer)
        m.plot()
        twt, li, vp, _, _, _ = m.realize_model(0.001)
        print(len(vp))
        fig, ax = plt.subplots()
        ax.plot(twt, vp / 1000., twt, li)

    def test_quasi2d_layer(self, unit_test=True):
        from blixt_geo_py.core.core import LithoFluid
        def vp(_i):
            return Q_(3000. +  5. * _i, 'm/s')
        def vs(_i):
            return Q_(1500. +  5. * _i, 'm/s')
        def rho(_i):
            return Q_(2.5 +  0.1 * _i, 'grams/cm^3')
        def thickness_m(_i):
            return Q_(30. + 2 * _i, 'm')
        def thickness_twt(_i):
            return Q_(40. + 2 * _i, 'milliseconds')

        lf = LithoFluid(vp=vp, vs=vs, rho=rho,
                        vp_std_dev=1., vs_std_dev=1., rho_std_dev=0.01,
                        vp_vs_cc=0.9, vp_rho_cc=0.9, vs_rho_cc=0.9)

        l_m = Layer(thickness=thickness_m, litho_fluid=lf)
        l_twt = Layer(thickness=thickness_twt, litho_fluid=lf)

    def test_quasi2d(self, unit_test=True):
        from bokeh.plotting import show, row, column
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable

        n_samplings = 11

        # for a wedge model to work, we need to counterweight the changing thickness of one layer with an extra layer
        # so that the total height of the model is kept constant
        def wedge(i):
            return Q_(50. - i, 'm')

        def reverse_wedge(i):
            return Q_(25. + i, 'm')

        def vp(i):
            # phi = np.linspace(0.1, 0.4, n_samplings)
            # k_eff, mu_eff = constantcement(37, 45, phi, apc=2)
            # # print(k_eff, mu_eff)
            # # print(v_p(k_eff[i], mu_eff[i], 2.3))
            # return 1000. * v_p(k_eff[i], mu_eff[i], 2.3)

            # gas lens (gas in the center, brine on the flanks):
            if (i > 17) and (i < 34):
                return Q_(3600., 'm/s')
            else:
                return Q_(3730., 'm/s')

        def vs(i):
            # phi = np.linspace(0.1, 0.4, n_samplings)
            # k_eff, mu_eff = constantcement(37, 45, phi, apc=2)
            # return 1000. * v_s(k_eff[i], 2.3)
            # gas lens:
            if (i > 17) and (i < 34):
                return Q_(2120., 'm/s')
            else:
                return Q_(2070., 'm/s')

        def rho(i):
            # gas lens:
            if (i > 17) and (i < 34):
                return Q_(2.2, 'grams/cm^3')
            else:
                return Q_(2.3, 'grams/cm^3')

        # Litho-fluids
        lfs = LithoFluids([
            LithoFluid(default='shale'),
            LithoFluid(name='Quasi 2D', vp=vp, vs=1800, rho=2.3),
            LithoFluid(name='Basement', vp=2800, vs=1350, rho=2.46)
        ])
        table_lf = LithoFluidsTable(lfs, width=300, advanced=False)
        cds_lf = table_lf.cds
        lf_table, lf_controls = table_lf.draw(cds_lf)

        # wedge model
        first_layer = Layer(name='First', thickness=Q_(50., 'm'), litho_fluid=lfs.litho_fluids[0])
        second_layer = Layer(name='Second', thickness=wedge, litho_fluid=lfs.litho_fluids[1])
        third_layer = Layer(name='Third', thickness=reverse_wedge, litho_fluid=lfs.litho_fluids[2])

        # # gas lens model
        # first_layer = Layer(thickness=Q_(0.05, 's'), vp=Q_(3400., 'm/s'), vs=Q_(1820., 'm/s'), rho=Q_(2.6, 'gram/cm^3'))
        # second_layer = Layer(thickness=Q_(0.03, 's'), vp=Q_(vp, 'm/s'), vs=Q_(vs, 'm/s'), rho=Q_(rho, 'gram/cm^3'), target=True)
        # third_layer = Layer(thickness=Q_(0.05, 's'), vp=Q_(3400., 'm/s'), vs=Q_(1820., 'm/s'), rho=Q_(2.6, 'gram/cm^3'))

        m = Model(depth_to_top=Q_(2000., 'm'), layers=[first_layer, second_layer, third_layer],
                  trace_index_range=np.arange(n_samplings))
        # m.plot()
        table_model = ModelTable(m)
        cds_model = table_model.cds
        model_table, model_controls = table_model.draw(cds_model, cds_lf)

        # wavelet = bumw.ricker(0.096, 0.001, 25)

        # plot_wiggles(m, 0.001, wavelet, angle=0., eei=True, scaling=80., extract_avo_at=[(8, 1.99), (24, 1.99)])
        # plot_wiggles(m, 0.001, wavelet, angle=15., eei=True, scaling=80., extract_avo_at=[(8, 1.99), (24, 1.99)])
        # plot_wiggles(m, 0.001, wavelet, angle=-90., eei=True, scaling=80., extract_avo_at=[(8, 1.99), (24, 1.99)])

        if unit_test:
            show(
                row(
                    column(model_table, model_controls),
                    column(lf_table, lf_controls)
                )
            )
            return None
        else:
            return model_table, model_controls, lf_table, lf_controls

    def test_saturation_wedge(self):
        from blixt_geo_py.rp.rp_core import rpt_parameters
        wavelet = bumw.ricker(0.096, 0.001, 25)
        dt = wavelet['header']['Sample rate']  # should be given in seconds
        rpts = rpt_parameters()
        m = build_saturation_wedge(
            2.0, 0.05, 0.9, 10,
            l1, l2, l1, 0.2, rpts)

        hc_sat = np.linspace(0, 0.9, 10)

        # for i in m.trace_index_range:
        #     print(i, m.layers[1].vp(i), m.layers[1].vs(i), m.layers[1].rho(i))
        fig, axs = plt.subplots(2, 2, figsize=(8, 8), gridspec_kw={'height_ratios': [2, 1], 'width_ratios': [1, 0.2]})
        axs[1, 1].set_axis_off()
        wiggle_ax = axs[0, 0]
        model_ax = axs[0, 1]
        wedge_ax = axs[1, 0]
        fig.subplots_adjust(wspace=0.)
        extract_avo_at = (1, 2.)
        plot_domain = 'TWT'
        overburden_vel = 3000.
        scaling = 10.
        avo_curves, amps, min_amps, max_amps, apparent_thickness = plot_wiggles(
            m, dt, wavelet, ax=wiggle_ax, extract_avo_at=extract_avo_at,
            plot_domain=plot_domain, overburden_vel=overburden_vel, scaling=scaling)
        wiggle_ax.set_ylim(wiggle_ax.get_ylim()[::-1])
        m[0].plot(ax=model_ax, kwargs1d={'yticks': False, 'legend': False})
        wedge_ax.plot(hc_sat, np.abs(np.array(min_amps)), label='|Min|')
        wedge_ax.set_ylabel('Amplitude')
        wedge_ax.set_xlabel('HC saturation')
        wedge_ax.legend(loc='upper left')
        show_or_close()

    def test_model_table(self, unit_test=True, only_verbatim=False):
        from bokeh.plotting import show, row, column

        # When creating output to Bokeh server, we need to set only_verbatim False
        if not unit_test:
            only_verbatim = False

        lfs = LithoFluids(
            [LithoFluid(default='shale'), LithoFluid(default='brine_sst'), LithoFluid(default='oil_sst')]
        )
        table_lf = LithoFluidsTable(lfs, width=300, advanced=False)
        cds_lf = table_lf.cds
        lf_table, lf_controls = table_lf.draw(cds_lf)

        # layers = [_lf.to_model_layer(_name) for _name, _lf in zip(['Top', 'Middle', 'Bottom'], lfs.litho_fluids)]
        layers = [
            LithoFluid(default='shale').to_model_layer('Top',thickness=Q_(50., 'm')),
            LithoFluid(default='brine_sst').to_model_layer('Reservoir',thickness=Q_(25., 'm')),
            LithoFluid(default='oil_sst').to_model_layer('Reservoir', case='Oil',thickness=Q_(25., 'm')),
            LithoFluid(default='shale').to_model_layer('Bottom',thickness=Q_(50., 'm')),
            LithoFluid(default='shale').to_model_layer('Basement',thickness=Q_(50., 'm'))
        ]
        # layers = []
        model = Model(layers=layers)
        table_model = ModelTable(model)
        cds_model = table_model.cds
        model_table, model_controls = table_model.draw(cds_model, cds_lf)

        if only_verbatim:
            for _key in list(cds_model.data.keys()):
                if _key == 'top' or _key == 'thickness':
                    print(_key)
                    print(cds_model.data[_key])
            realized_cases = table_model.realize(Q_(5.0, 'm'))
            # for _key in list(realized_cases.keys()):
            #     print(_key)
            #     print(realized_cases[_key]['vp'].values)
        else:
            if unit_test:
                show(
                    row(
                        column(model_table, model_controls),
                        column(lf_table, lf_controls)
                    )
                )
                return None
            else:
                return model_table, model_controls, lf_table, lf_controls
        return None

    def test_laminar_model(self, unit_test=True):
        from bokeh.plotting import show, row, column

        # Create the laminar model
        lm = LaminarModel(resolution=Q_(0.1, 'm'), layers_width=0., avo_or_eei='avo')

        (title, lf_table, lf_controls, model_table, model_controls, grid,
         controls, seismic_cds) = lm.draw()

        if unit_test:
            show(column(column(title, grid, sizing_mode='stretch_width'), controls,
                        row(
                            column(model_table, model_controls),
                            column(lf_table, lf_controls)
                        ))
                 )
            return None
        else:
            return title, model_table, model_controls, lf_table, lf_controls, grid, controls

    def test_laminar_model_title(self):
        lm = LaminarModel(resolution=Q_(0.1, 'm'), avo_or_eei='avo')
        self.assertIn('Default model', lm.draw()[0].text)

        lm_2d = LaminarModel(
            model=Model(layers=[layer1, layer2, layer5], name='Q2D model', trace_index_range=np.arange(3)),
            resolution=Q_(0.1, 'm'), avo_or_eei='avo')
        self.assertIn('Q2D model', lm_2d.draw_2d()[0].text)

        lm.model.name = None
        self.assertEqual(lm.title_div().text, '')

    def test_wedge_model_title(self):
        self.assertIn('Wedge model', WedgeModel(n_traces=5).draw()[0].text)
        self.assertIn('My wedge', WedgeModel(n_traces=5, name='My wedge').draw()[0].text)

    def test_model_name_survives_table_update(self):
        lm = LaminarModel(resolution=Q_(0.1, 'm'), avo_or_eei='avo')
        model_controls = lm.draw()[4]
        layers_before = lm.model_table.model.layers
        for _callback in model_controls.children[2]._event_callbacks['button_click']:
            _callback()
        # The table has built a new Model
        self.assertIsNot(lm.model_table.model.layers, layers_before)
        self.assertEqual(lm.model_table.model.name, 'Default model')

    def test_layer_names_data(self):
        # Only the base case layers are listed, stacked from the top of the model
        model = Model(layers=[layer1, layer2, layer3, layer5])
        top = model.depth_to_top.to('m').magnitude
        data = layer_names_data(model)
        self.assertEqual(['Top', 'Reservoir', 'Basement'], data['name'])
        np.testing.assert_allclose([top, top + 50., top + 70.], data['top'])
        np.testing.assert_allclose([top + 50., top + 70., top + 120.], data['base'])
        np.testing.assert_allclose([top + 25., top + 60., top + 95.], data['mid'])

        # In a quasi 2D model, the layers follow the given lateral index
        wedge = Layer('Wedge', 'Base', thickness=lambda _i: Q_(20. - _i, 'm'), litho_fluid=l2)
        q2d_model = Model(layers=[layer1, wedge, layer5], trace_index_range=np.arange(5))
        np.testing.assert_allclose([50., 17., 50.], layer_names_data(q2d_model, 3)['thickness'])

    def test_laminar_model_layer_names(self):
        from bokeh.models import Rect, Text, DataTable
        from blixt_geo_py.plotting.log_plotter import select_column

        def layer_glyph_sources(_grid):
            # Returns the data sources of the boxes and the names in the LAYERS column
            _p = select_column(_grid, 'LAYERS')
            self.assertIsNotNone(_p)
            _sources = {type(_r.glyph): _r.data_source for _r in _p.renderers}
            self.assertIs(_sources[Rect], _sources[Text])
            return _sources[Rect]

        lm = LaminarModel(resolution=Q_(0.1, 'm'), avo_or_eei='avo')
        draw_output = lm.draw()
        layers_cds = layer_glyph_sources(draw_output[5])
        self.assertEqual(['Top', 'Reservoir', 'Bottom'], layers_cds.data['name'])

        # An edit of the model table (a 'patching' event) updates the colors and names of the layers in the browser,
        # like the working intervals table does
        model_cds = draw_output[3].select_one({'type': DataTable}).source
        callbacks = [_c for _c in model_cds.js_property_callbacks.get('patching', []) if _c.args.get('layers') is not None]
        self.assertEqual(1, len(callbacks))
        self.assertIs(layers_cds, callbacks[0].args['layers'])
        self.assertIs(model_cds, callbacks[0].args['model'])
        # The names are still there after the model is updated from the table
        for _callback in draw_output[4].children[2]._event_callbacks['button_click']:
            _callback()
        self.assertEqual(['Top', 'Reservoir', 'Bottom'], layers_cds.data['name'])

        # In the quasi 2D model, the layer boxes follow the selected trace
        wedge = Layer('Wedge', 'Base', thickness=lambda _i: Q_(20. - _i, 'm'), litho_fluid=l2)
        lm_2d = LaminarModel(
            model=Model(layers=[layer1, wedge, layer5], name='Q2D model', trace_index_range=np.arange(5)),
            resolution=Q_(0.1, 'm'), avo_or_eei='avo')
        draw_output = lm_2d.draw_2d()
        layers_cds = layer_glyph_sources(draw_output[5])
        np.testing.assert_allclose([50., 20., 50.], layers_cds.data['thickness'])
        trace_selector = draw_output[6].children[0]
        trace_selector.value = '3'
        np.testing.assert_allclose([50., 17., 50.], layers_cds.data['thickness'])

    def test_laminar_model_dx(self):
        from bokeh.models import GlyphRenderer
        from bokeh.models.glyphs import Image
        from blixt_geo_py.plotting.log_plotter import select_column

        wedge = Layer('Wedge', 'Base', thickness=lambda _i: Q_(20. - _i, 'm'), litho_fluid=l2)
        lm_2d = LaminarModel(
            model=Model(layers=[layer1, wedge, layer5], trace_index_range=np.arange(5)),
            resolution=Q_(0.1, 'm'))
        draw_output = lm_2d.draw_2d()
        _p = select_column(draw_output[5], 'SYNTH_2D')
        image = [_r.glyph for _r in _p.renderers
                 if isinstance(_r, GlyphRenderer) and isinstance(_r.glyph, Image)][0]
        trace_selector = draw_output[6].children[0]
        dx_selector = draw_output[6].children[4]
        self.assertEqual(['None', '5', '12.5', '25', '50', '100'], dx_selector.options)

        # Without dx, the lateral axis is the trace index, as before
        self.assertEqual('None', dx_selector.value)
        self.assertEqual((0., 5.), (image.x, image.dw))
        self.assertEqual((0., 5.), (_p.x_range.start, _p.x_range.end))
        self.assertEqual(['0', '1', '2', '3', '4'], [_o[1] for _o in trace_selector.options])
        self.assertEqual(2, lm_2d.trace_index_from_x(2.7))

        # With dx, the traces are centered at trace_index * dx
        trace_selector.value = '3'
        dx_selector.value = '25'
        self.assertEqual(Q_(25., 'm'), lm_2d.dx)
        self.assertEqual((-12.5, 125.), (image.x, image.dw))
        self.assertEqual((-12.5, 112.5), (_p.x_range.start, _p.x_range.end))
        self.assertEqual(['0 (0 m)', '1 (25 m)', '2 (50 m)', '3 (75 m)', '4 (100 m)'],
                         [_o[1] for _o in trace_selector.options])
        self.assertEqual(['0', '1', '2', '3', '4'], [_o[0] for _o in trace_selector.options])
        self.assertEqual('3', trace_selector.value)
        self.assertEqual(3, lm_2d.trace_index_from_x(80.))

        # And back again
        dx_selector.value = 'None'
        self.assertIsNone(lm_2d.dx)
        self.assertEqual((0., 5.), (_p.x_range.start, _p.x_range.end))

        # A dx which is not among the default options is added to them, and a FaultModel can not have dx = None
        lm_2d = LaminarModel(
            model=Model(layers=[layer1, wedge, layer5], trace_index_range=np.arange(5)),
            resolution=Q_(0.1, 'm'), dx=Q_(10., 'm'))
        self.assertEqual(['None', '5', '10', '12.5', '25', '50', '100'], lm_2d.draw_2d()[6].children[4].options)
        self.assertNotIn('None', FaultModel(n_traces=51).draw_2d()[6].children[4].options)

    def test_laminar_model_layers_width(self):
        from blixt_geo_py.plotting.log_plotter import select_column

        # The width of the layer names column is relative to a synthetic column, and the synthetic columns keep their
        # width
        widths = {}
        for _layers_width in [0.25, 0.5]:
            grid = LaminarModel(resolution=Q_(0.1, 'm'), layers_width=_layers_width).draw()[5]
            synth_width = select_column(grid, 'SYNTH_BASE').width
            self.assertAlmostEqual(_layers_width, select_column(grid, 'LAYERS').width / synth_width, delta=0.01)
            widths[_layers_width] = synth_width
        self.assertAlmostEqual(widths[0.25], widths[0.5], delta=2)

        wedge = Layer('Wedge', 'Base', thickness=lambda _i: Q_(20. - _i, 'm'), litho_fluid=l2)
        grid = LaminarModel(
            model=Model(layers=[layer1, wedge, layer5], trace_index_range=np.arange(5)),
            resolution=Q_(0.1, 'm'), layers_width=0.5).draw_2d()[5]
        self.assertAlmostEqual(0.5 / 1.4, select_column(grid, 'LAYERS').width / select_column(grid, 'SYNTH_2D').width,
                               delta=0.01)

        # A width of 0 leaves the column out
        self.assertIsNone(select_column(LaminarModel(resolution=Q_(0.1, 'm'), layers_width=0).draw()[5], 'LAYERS'))
        grid = LaminarModel(
            model=Model(layers=[layer1, wedge, layer5], trace_index_range=np.arange(5)),
            resolution=Q_(0.1, 'm'), layers_width=0).draw_2d()[5]
        self.assertIsNone(select_column(grid, 'LAYERS'))

    def test_model_name_survives_taking_a_trace(self):
        model = Model(layers=[layer1, layer2, layer5], name='Q2D model', trace_index_range=np.arange(3))
        self.assertEqual(model[1].name, 'Q2D model')

    def test_laminar_model_with_avo_points(self, unit_test=True):
        from bokeh.plotting import show, row, column

        # Create the laminar model
        lm = LaminarModel(resolution=Q_(0.1, 'm'), avo_or_eei='avo')

        (title, lf_table, lf_controls, model_table, model_controls, grid,
         controls, seismic_cds) = lm.draw()

        # Test adding some extraction points
        analyze_avo = AvoAnalyzer(grid, 'avo section', None, model=lm)
        points_cds = analyze_avo.cds
        points_table, update_avo, avo_figure, ixg_figure, eei_figure, chi_input, avo_cds = analyze_avo.draw(points_cds, seismic_cds)

        if unit_test:
            show(
                row(
                    column(
                        column(title, grid, sizing_mode='stretch_width'),
                        controls,
                        row(
                            column(model_table, model_controls),
                            column(lf_table, lf_controls)
                        )
                    ),
                    column(points_table, row(update_avo, chi_input), avo_figure, ixg_figure, eei_figure)
                )
            )
            return None
        else:
            return (title, model_table, model_controls, lf_table, lf_controls, grid, controls,
                    points_table, update_avo, avo_figure, ixg_figure, eei_figure, chi_input, avo_cds)

    def test_laminar_q2d_model(self, unit_test=True):
        from bokeh.plotting import show, row, column

        def vp(_i):
            return Q_(3000. +  5. * _i, 'm/s')
        def vs(_i):
            return Q_(1500. +  5. * _i, 'm/s')
        def rho(_i):
            return Q_(2.5 +  0.1 * _i, 'grams/cm^3')
        def wedge(i):
            return Q_(50. - i, 'm')
        def reverse_wedge(i):
            return Q_(25. + i, 'm')

        # Litho-fluids
        lfs = LithoFluids([
            LithoFluid(default='shale'),
            LithoFluid(default='oil_sst'),
            LithoFluid(name='Quasi 2D', vp=vp, vs=vs, rho=rho),
            LithoFluid(name='Basement', vp=2800, vs=1350, rho=2.46)
        ])

        # wedge model
        first_layer = Layer(name='First', thickness=Q_(50., 'm'), litho_fluid=lfs.litho_fluids[0])
        second_layer = Layer(name='Second', thickness=wedge, litho_fluid=lfs.litho_fluids[2])
        second_layer_oil = Layer(name='Second', case='Oil', thickness=wedge, litho_fluid=lfs.litho_fluids[1])
        third_layer = Layer(name='Third', thickness=reverse_wedge, litho_fluid=lfs.litho_fluids[3])
        layers = [first_layer, second_layer, second_layer_oil, third_layer]
        model = Model(layers=layers, trace_index_range=np.arange(11))

        # Create the laminar model
        lm = LaminarModel(model=model, litho_fluids=lfs, resolution=Q_(0.1, 'm'), dx=Q_(10., 'm'), avo_or_eei='avo')

        # lf_table, add_row, delete_row, update, model_table, add_row_m, delete_row_m, update_m, grid, controls = lm.draw()
        (title, lf_table, lf_controls, model_table, model_controls, grid, controls,
         synth_2d_cds) = lm.draw_2d()

        if unit_test:
            show(column(title, grid, controls,
                row(
                    column(model_table, model_controls),
                    column(lf_table, lf_controls)
                ))
            )
            return None
        else:
            return title, model_table, model_controls, lf_table, lf_controls, grid, controls

    def test_wedge(self, unit_test=True):
        from bokeh.plotting import show, row, column
        wm = WedgeModel(n_traces=51)
        title, lf_table, lf_controls, model_table, model_controls, grid, controls, new_grid, synth_2d_cds = wm.draw()

        wm.model.plot()
        show_or_close()

        # Test adding some extraction points
        analyze_avo = AvoAnalyzer(grid, 'line section', None, model=wm)
        points_cds = analyze_avo.cds
        points_table, update_avo, avo_figure, ixg_figure, eei_figure, chi_input, avo_cds = analyze_avo.draw(points_cds, synth_2d_cds)
        if unit_test:
            show(row(
                column(title, grid, controls, new_grid,
                        row(
                            column(model_table, model_controls),
                            column(lf_table, lf_controls)
                        )),
                 column(points_table, row(update_avo, chi_input), avo_figure, ixg_figure, eei_figure))
                 )
            return None
        else:
            return (title, model_table, model_controls, lf_table, lf_controls, grid, controls, new_grid, points_table,
                    update_avo, avo_figure, ixg_figure, eei_figure, chi_input)

    def test_catch_change_in_cases(self):
        prev_cases = [[1, 2], [1,2,3], [1,2], [1,4]]
        new_cases =  [[1,2], [1,2], [1,2,3], [1,3]]
        for new_case, prev_case in zip(new_cases, prev_cases):
            _dict = detect_change_in_cases(new_case, prev_case)
            print('New:', _dict['new'], ', Removed: ', _dict['removed'])

    def test_horizon_cds(self):
        def wedge(i):
            return Q_(50. - i, 'm')
        def reverse_wedge(i):
            return Q_(25. + i, 'm')
        first_layer = Layer(name='First', thickness=Q_(50., 'm'), litho_fluid=LithoFluid(default='shale'))
        second_layer = Layer(name='Second', thickness=wedge, litho_fluid=LithoFluid(default='brine_sst'))
        second_layer_oil = Layer(name='Second', case='Oil', thickness=wedge, litho_fluid=LithoFluid(default='oil_sst'))
        third_layer = Layer(name='Third', thickness=reverse_wedge, litho_fluid=LithoFluid(default='shale'))
        layers = [first_layer, second_layer, second_layer_oil, third_layer]
        model = Model(layers=layers, trace_index_range=np.arange(11))
        cds = model.horizons_cds()
        for _key in list(cds.data.keys()):
            print(_key, cds.data[_key])

    def test_fault_model(self, unit_test=True):
        from bokeh.plotting import show, row, column
        dip = Q_(60., 'deg')
        depth_to_top = Q_(3000., 'm')
        dx = Q_(12.5, 'm')
        #   dx = Q_(2.5, 'm')
        n_traces = 51

        fm = FaultModel(
            dx=dx,
            depth_to_top=depth_to_top,
            dip=dip,
            n_traces=n_traces
        )

        (title, lf_table, lf_controls, model_table,
                model_controls, grid,
                controls, synth_2d_cds,
                dip_selector, throw_selector, n_traces_selector) = fm.draw()

        if unit_test:
            show(
                row(
                    column(
                        column(title, grid, sizing_mode='stretch_width'),
                        controls,
                            row(
                                column(model_table, model_controls),
                                column(lf_table, lf_controls)
                            )),
                     column(dip_selector, throw_selector, n_traces_selector)
                 ))
            return None
        else:
            return (title, lf_table, lf_controls, model_table,
                 model_controls, grid,
                 controls, synth_2d_cds,
                 dip_selector, throw_selector, n_traces_selector)

    def test_faulted_horizons(self):
        from blixt_geo_py.core.models import faulted_layer_top, faulted_layer_thickness
        T = [30., 50., 50., 30.]
        n_layers = len(T)

        D = 20  # vertical throw [m]

        fault_dip = 60
        x_fault_top = 100


        x = np.linspace(0,400,50)

        fig, axs = plt.subplots(2, 1, figsize=(10,10))

        for i in range(0,n_layers+1):

            h = faulted_layer_top(
                x,
                i,
                T,
                D,
                np.radians(fault_dip),
                x_fault_top,
                None
            )

            axs[0].plot(x, h, label=f"Interface {i}")

            if i < n_layers:
                _thick = faulted_layer_thickness(
                    x,
                    i,
                    T,
                    D,
                    np.radians(fault_dip),
                    x_fault_top
                )

                axs[1].plot(x, _thick, label=f"Layer {i}")

        # fault
        zf = np.linspace(
            0,
            sum(T) + D,
            200
        )

        xf = (
                x_fault_top
                + zf/np.tan(
            np.radians(fault_dip)
        )
        )

        axs[0].plot(
            xf,
            zf,
            'r--',
            lw=2
        )

        axs[0].invert_yaxis()
        axs[0].legend()
        axs[0].set_aspect('equal')

        axs[1].legend()

        show_or_close()

    def test_save_model(self, unit_test=True):
        from bokeh.plotting import show, row, column

        lfs = LithoFluids(
            [LithoFluid(default='shale'), LithoFluid(default='brine_sst'), LithoFluid(default='oil_sst')]
        )
        table_lf = LithoFluidsTable(lfs, width=300, advanced=False)
        cds_lf = table_lf.cds
        lf_table, lf_controls = table_lf.draw(cds_lf)

        layers = [
            LithoFluid(default='shale').to_model_layer('Top',thickness=Q_(50., 'm')),
            LithoFluid(default='brine_sst').to_model_layer('Reservoir',thickness=Q_(25., 'm')),
            LithoFluid(default='oil_sst').to_model_layer('Reservoir', case='Oil',thickness=Q_(25., 'm')),
            LithoFluid(default='shale').to_model_layer('Bottom',thickness=Q_(50., 'm')),
            LithoFluid(default='shale').to_model_layer('Basement',thickness=Q_(50., 'm'))
        ]
        # layers = []
        model = Model(layers=layers)
        table_model = ModelTable(model)
        cds_model = table_model.cds
        # model_table, add_row_m, delete_row_m, update_m = table_model.draw(cds_model, cds_lf)
        model_table, model_controls = table_model.draw(cds_model, cds_lf)

        if unit_test:
            show(
                row(
                    column(model_table, model_controls),
                    column(lf_table, lf_controls)
                )
            )
            return None
        else:
            return model_table, model_controls, lf_table, lf_controls

