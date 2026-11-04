import os
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
import blixt_geo_py.unit_tests.plot_settings  # noqa: F401

import numpy as np

from blixt_geo_py.plotting.cross_plotter import CrossPlotter, DataSource

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))


def make_data_sources(size_1: int = 500, size_2: int = 800):
    from blixt_geo_py.core.core import Template, StratUnit, Interval, Intervals, CutoffRule, Cutoffs
    from blixt_geo_py import Q_
    md1 = Q_(np.linspace(1000., 2000., size_1), 'm')
    md2 = Q_(np.linspace(800., 2500., size_2), 'm')
    l1_1 = Q_(np.random.normal(10., 1., size_1), 'm')
    l1_2 = Q_(np.random.normal(10., 1., size_2), 'm')
    l2_1 = Q_(np.random.normal(100., 1., size_1) + np.linspace(-8, 8, size_1), 'm/s')
    l2_2 = Q_(np.random.normal(100., 1., size_2) + np.linspace(-10, 10, size_2), 'm/s')
    l3 = Q_(np.random.normal(50., 1., size_1), 'kg')
    l4 = Q_(np.random.normal(70., 1., size_2), 'feet')

    template_md = Template(name='md', units='m', marker='circle', fill_color='red')
    template_one = Template(name='var_one', units='m', min=5., max=15., marker='circle', fill_color='red')
    template_two = Template(name='var_two', units='m/s', min=90., max=110., marker='square', fill_color='blue')
    template_three = Template(name='var_three', units='kg', min=10., max=80., marker='triangle', fill_color='yellow')
    template_four = Template(name='var_four', units='feet', min=30., max=90., marker='hex', fill_color='green')

    data_one = dict(md=md1, var_one=l1_1, var_two=l2_1, var_three=l3)
    data_two = dict(md=md2, var_one=l1_2, var_two=l2_2, var_four=l4)
    templates_one = {_x.name: _x for _x in [template_md, template_one, template_two, template_three]}
    templates_two = {_x.name: _x for _x in [template_md, template_one, template_two, template_four]}

    ds1 = DataSource(name='one', data=data_one, templates=templates_one)
    ds2 = DataSource(name='two', data=data_two, templates=templates_two)

    wis = Intervals(
        name='test', intervals=[
            Interval( well='one', top=Q_(1350, 'm'), base=Q_(1450, 'm'), interval_info=StratUnit('wi_1', 1)),
            Interval( well='one', top=Q_(1550, 'm'), base=Q_(1750, 'm'), interval_info=StratUnit('wi_2', 1)),
            Interval( well='two', top=Q_(1500, 'm'), base=Q_(1900, 'm'), interval_info=StratUnit('wi_1', 1)),
            Interval( well='two', top=Q_(1100, 'm'), base=Q_(1450, 'm'), interval_info=StratUnit('wi_2', 1)),
            Interval(well='two', top=Q_(850, 'm'), base=Q_(1550, 'm'), interval_info=StratUnit('wi_3', 1))
        ] )

    rule1 = CutoffRule('var_one', '>', Q_(10, 'm'))
    rule2 = CutoffRule('var_two', '<', Q_(101, 'm/s'))
    cutoffs = Cutoffs(cutoffs=[rule1, rule2])

    return ds1, ds2, wis, cutoffs


class TestBehaviour(unittest.TestCase):
    """
    Checks the results of CrossPlotter, without needing any data files or looking at a plot
    """
    @staticmethod
    def _source(name='a', **data):
        from blixt_geo_py import Q_
        return DataSource(name=name, data={_key: Q_(np.array(_val), _unit) for _key, (_val, _unit) in data.items()})

    def test_variables_keep_the_order_of_the_first_source(self):
        ds1, ds2, _, _ = make_data_sources(size_1=3, size_2=4)
        xp = CrossPlotter({_s.name: _s for _s in [ds1, ds2]})
        self.assertEqual(xp.common_variables, ['md', 'var_one', 'var_two'])
        self.assertEqual(xp.all_variables, ['md', 'var_one', 'var_two', 'var_three', 'var_four'])
        self.assertEqual((xp.x, xp.y), ('md', 'var_one'))

    def test_default_y_differs_from_x(self):
        ds1, ds2, _, _ = make_data_sources(size_1=3, size_2=4)
        xp = CrossPlotter({_s.name: _s for _s in [ds1, ds2]}, x='var_one')
        self.assertEqual((xp.x, xp.y), ('var_one', 'md'))

    def test_too_few_common_variables_gives_clear_error(self):
        with self.assertRaisesRegex(IOError, 'at least two variables'):
            CrossPlotter({'a': self._source(p=([1.], 'm'))})

    def test_min_and_max_of_values_outside_one_million(self):
        xp = CrossPlotter({'a': self._source(p=([2e9, 3e9], 'Pa'), q=([-5e6, -4e6], 'm'))})
        min_max = xp.min_and_max()
        self.assertEqual(min_max['p'], [2e9, 3e9])
        self.assertEqual(min_max['q'], [-5e6, -4e6])

    def test_min_and_max_of_data_without_units(self):
        ds = DataSource(name='a', data=dict(p=np.array([1., 2.]), q=np.array([3., 4.])))
        self.assertEqual(CrossPlotter({'a': ds}).min_and_max()['q'], [3., 4.])

    def test_min_and_max_ignores_invalid_values(self):
        xp = CrossPlotter({'a': self._source(p=([1., np.nan, np.inf], 'm'), q=([np.nan, np.nan, np.nan], 'm'))})
        min_max = xp.min_and_max()
        self.assertEqual(min_max['p'], [1., 1.])
        self.assertEqual(min_max['q'], [None, None])

    def test_cds_uses_the_mask_of_the_data_sources(self):
        from blixt_geo_py import Q_
        ds = DataSource(name='a', data=dict(p=Q_(np.array([1., 2.]), 'm'), q=Q_(np.array([3., 4.]), 'm')),
                        mask=np.array([True, False]))
        self.assertEqual(list(CrossPlotter({'a': ds}).cds.data['mask']), [True, False])

    def test_cds_converts_all_sources_to_the_units_of_the_template(self):
        from blixt_geo_py import Q_
        from blixt_geo_py.core.core import Template
        ds_m = DataSource(name='in_m', data=dict(d=Q_(np.array([1000.]), 'm'), q=Q_(np.array([1.]), 'm')),
                          templates={'d': Template(name='d', units='m')})
        ds_ft = DataSource(name='in_ft', data=dict(d=Q_(np.array([1000.]), 'feet'), q=Q_(np.array([1.]), 'm')))
        xp = CrossPlotter({'in_m': ds_m, 'in_ft': ds_ft}, x='d', y='q')
        np.testing.assert_allclose(xp.cds.data['d'], [1000., 304.8])
        np.testing.assert_allclose(xp.min_and_max()['d'], [304.8, 1000.])

    def test_incompatible_units_keep_their_values(self):
        ds_1 = self._source('one', d=([1.], 'm'), q=([1.], 'm'))
        ds_2 = self._source('two', d=([2.], 'kg'), q=([1.], 'm'))
        xp = CrossPlotter({'one': ds_1, 'two': ds_2}, x='d', y='q')
        np.testing.assert_allclose(xp.cds.data['d'], [1., 2.])

    def test_each_data_source_has_its_own_legend_item(self):
        ds1, ds2, _, _ = make_data_sources(size_1=3, size_2=4)
        xp = CrossPlotter({_s.name: _s for _s in [ds1, ds2]})
        xplot = xp.draw(xp.cds)[0]
        items = xplot.legend[0].items
        self.assertEqual([_item.label.value for _item in items], ['one', 'two'])
        self.assertEqual([len(_item.renderers) for _item in items], [1, 1])
        self.assertIsNot(items[0].renderers[0], items[1].renderers[0])
        self.assertEqual(xplot.legend[0].click_policy, 'hide')

    def test_size_menu_starts_at_the_plotted_size(self):
        ds1, ds2, _, _ = make_data_sources(size_1=3, size_2=4)
        xp = CrossPlotter({_s.name: _s for _s in [ds1, ds2]})
        cds = xp.cds
        size_menu = xp.draw(cds)[3]
        self.assertEqual(float(size_menu.value), cds.data['size'][0])

    def test_axis_label_without_template_or_units(self):
        from blixt_geo_py.core.core import Template
        ds = self._source(p=([1., 2.], 'm'), q=([3., 4.], 'm'))
        ds.templates = {'q': Template(name='q')}
        xp = CrossPlotter({'a': ds}, x='p', y='q')
        xplot = xp.draw(xp.cds)[0]
        self.assertEqual(xplot.xaxis[0].axis_label, 'p')
        self.assertEqual(xplot.yaxis[0].axis_label, 'q')

    def test_axis_limits_from_template_or_padded_data(self):
        from bokeh.models import Range1d
        from blixt_geo_py.core.core import Template
        ds = self._source(p=([0., 10.], 'm'), q=([3., 3.], 'm'), r=([np.nan, np.nan], 'm'))
        ds.templates = {'p': Template(name='p', units='m', min=-1., max=20.), 'q': Template(name='q', units='m')}
        xp = CrossPlotter({'a': ds}, x='p', y='q')
        limits = xp.axis_limits()
        self.assertEqual(limits['p'], [-1., 20.])
        self.assertEqual(limits['q'], [2.5, 3.5])
        self.assertEqual(limits['r'], [None, None])
        xplot = xp.draw(xp.cds)[0]
        self.assertIsInstance(xplot.x_range, Range1d)
        self.assertEqual((xplot.x_range.start, xplot.x_range.end), (-1., 20.))

    def test_draw_with_a_variable_without_valid_data(self):
        ds = self._source(p=([np.nan, np.nan], 'm'), q=([3., 4.], 'm'))
        xp = CrossPlotter({'a': ds}, x='p', y='q')
        xplot = xp.draw(xp.cds)[0]
        self.assertNotIsInstance(xplot.x_range, type(xplot.y_range))

    def _click_apply_masks(self, ds, wis):
        xp = CrossPlotter({ds.name: ds}, working_intervals=wis)
        cds = xp.cds
        apply_mask = xp.draw(cds)[5]
        for _handler in apply_mask._event_callbacks['button_click']:
            _handler()
        self.assertEqual(len(cds.data['mask']), len(ds))

    def test_apply_masks_with_depth_named_dept(self):
        from blixt_geo_py import Q_
        from blixt_geo_py.core.core import Interval, Intervals, StratUnit
        wis = Intervals(name='test', intervals=[
            Interval(well='one', top=Q_(1350, 'm'), base=Q_(1450, 'm'), interval_info=StratUnit('wi_1', 1))])
        ds = self._source('one', dept=([1000., 1400., 1600.], 'm'), q=([1., 2., 3.], 'm'))
        self.assertEqual(CrossPlotter({'one': ds}).depth_variable, 'dept')
        self._click_apply_masks(ds, wis)

    def test_apply_masks_without_depth(self):
        from blixt_geo_py import Q_
        from blixt_geo_py.core.core import Interval, Intervals, StratUnit
        wis = Intervals(name='test', intervals=[
            Interval(well='one', top=Q_(1350, 'm'), base=Q_(1450, 'm'), interval_info=StratUnit('wi_1', 1))])
        ds = self._source('one', p=([1., 2., 3.], 'm'), q=([1., 2., 3.], 'm'))
        self.assertIsNone(CrossPlotter({'one': ds}).depth_variable)
        self._click_apply_masks(ds, wis)

    def test_draw_twice_with_default_tools(self):
        from bokeh.document import Document
        ds1, ds2, _, _ = make_data_sources(size_1=3, size_2=4)
        xp = CrossPlotter({_s.name: _s for _s in [ds1, ds2]})
        for _ in range(2):
            Document().add_root(xp.draw(xp.cds)[0])


class TestCases(unittest.TestCase):
    def test_data_cds(self):

        small = True
        if small:
            ds1, ds2, wis, cutoffs = make_data_sources(size_1=10, size_2=12)
        else:
            ds1, ds2, wis, cutoffs = make_data_sources()

        xp = CrossPlotter({_s.name:_s for _s in [ds1, ds2]})
        # print(xp.all_variables)
        # print(xp.common_variables)
        # print(xp.templates)
        print(len(xp), xp.all_variables, xp.common_variables, xp.common_units)
        d = xp.cds
        _dict = dict(d.data)
        for _key, _item in _dict.items():
            print(_key, _item[:5], _item[-5:], len(_item))
        print('XXX')
        # _d = add_x_y_to_cds(_dict, x='var_one', y='var_two')
        # for _key, _item in _d.items():
        #     print(_key, _item[:5], _item[-5:], len(_item))
        # xp.show_plot('C:\\Users\marte\Downloads\plot.html')
        xp.show_plot(d, os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))

    def test_from_las(self):
        from blixt_geo_py.core.well import Well
        las_fileA = os.path.join(project_dir, "blixt_geo_py\\test_data\\Well A.las")
        w = Well()
        w.read_las(las_fileA, True)
        xp = CrossPlotter(
            {w.name: w.data_source()}
        )
        cds = xp.cds
        xp.show_plot(cds, os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))

    def test_from_well(self):
        from blixt_geo_py.core.project import Project
        from blixt_geo_py.core.core import LogTable, Intervals

        project_table = os.path.join(project_dir, 'blixt_geo_py\\excels\\project_table.xlsx')

        project = Project(
            name='testing',
            working_dir= os.path.join(project_dir, 'blixt_geo_py'),
            project_table=project_table
        )
        log_table = LogTable({'Density': 'rho_dry', 'P velocity': 'vp_dry', 'S velocity': 'vs_dry',
                              'Porosity': 'PHIE', 'Volume': 'VCL'})

        wis = Intervals()
        wis.read_blixt_tops(project.project_table)

        project.load_all_wells(log_table=log_table)
        assert project.wells is not None
        # print([(w.name, list(w.style.keys()), w.style.full_name) for w in project.wells])
        xp = CrossPlotter(
            {w.name: w.data_source() for w in project.wells}
        )
        cds = xp.cds
        xp.show_plot(cds, os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))

    def test_data_classification(self):
        ds1, ds2, wis, cutoffs = make_data_sources()

        xp = CrossPlotter({_s.name:_s for _s in [ds1, ds2]}, cutoffs=cutoffs)
        d_cds = xp.cds

        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = xp.draw(d_cds)

        return xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis

    def test_working_intervals(self):
        ds1, ds2, wis, cutoffs = make_data_sources()
        xp = CrossPlotter({_s.name:_s for _s in [ds1, ds2]}, working_intervals=wis)
        d_cds = xp.cds

        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = xp.draw(d_cds)

        return xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, wis_guis

    def test_both(self):
        small = True
        if small:
            ds1, ds2, wis, cutoffs = make_data_sources(size_1=10, size_2=12)
        else:
            ds1, ds2, wis, cutoffs = make_data_sources()

        xp = CrossPlotter({_s.name:_s for _s in [ds1, ds2]}, cutoffs=cutoffs, working_intervals=wis)
        d_cds = xp.cds

        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = (
            xp.draw(d_cds, verbose=True))

        return xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis


    def test_moduli(self):
        from blixt_geo_py.core.well import Well
        from blixt_geo_py.core.core import LogTable
        from blixt_geo_py.rp.rp_wrapper import data_source_moduli
        las_fileA = os.path.join(project_dir, "blixt_geo_py\\test_data\\Well A.las")
        w = Well()
        w.read_las(las_fileA, True)
        lt1 = LogTable(name='ptb5', log_table={'P velocity': 'vp_ptb5', 'S velocity': 'vs_ptb5', 'Density': 'rho_ptb5'})
        wds1 = w.data_source(log_table=lt1, verbose=False)
        data_source_moduli(wds1, lt1, verbose=False)
        lt2 = LogTable(name='so08', log_table={'P velocity': 'vp_so08', 'S velocity': 'vs_so08', 'Density': 'rho_so08'})
        wds2 = w.data_source(log_table=lt2, verbose=True)
        data_source_moduli(wds2, lt2, verbose=False)
        lt3 = LogTable(name='sg08', log_table={'P velocity': 'vp_sg08', 'S velocity': 'vs_sg08', 'Density': 'rho_sg08'})
        wds3 = w.data_source(log_table=lt3, verbose=False)
        data_source_moduli(wds3, lt3, verbose=False)

        xp = CrossPlotter(
            {wds.name: wds for wds in [wds1, wds2, wds3]}
            # {wds.name: wds for wds in [wds1]}
        )
        cds = xp.cds
        xp.show_plot(cds, os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))
