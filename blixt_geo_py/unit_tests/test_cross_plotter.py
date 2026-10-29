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
