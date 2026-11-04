import os
import unittest
from copy import deepcopy
from unittest.mock import patch

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
from blixt_geo_py.unit_tests.plot_settings import show_or_close

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from bokeh.models import ColumnDataSource
from bokeh.plotting import show

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))

from blixt_geo_py import Q_
from blixt_geo_py.core.core import (Interval, StratUnit, Intervals, Template, Header, CutoffRule, Cutoffs, LogTable,
                                templates_from_table)


test_file_dir = str(os.path.dirname(__file__).replace(
    'blixt_geo_py\\unit_tests',
    'test_data'))

project_table = os.path.join(test_file_dir.replace('test_data', 'excels'), 'project_table.xlsx')

las_file1 = os.path.join(test_file_dir, "L-30.las")
las_file2 = "T:\\ROKDOC\\PL936\\To Partners from Ikon\\To Partners\\las files\\6406_11_1s.las"

rule1 = CutoffRule('name1', '>', Q_(100, 'm'))
rule2 = CutoffRule('name2', '<', Q_(10, 'm'))
rule3 = CutoffRule('name3', '==', Q_(1000, 'm'))
rule4 = CutoffRule('name4', None, 'my_interval')
rule5 = CutoffRule('name5', '><', [Q_(10, 'm'), Q_(1000, 'm')])
rule6 = CutoffRule('P velocity', '><', [Q_(10, 'm/s'), Q_(1000, 'm/s')])
rule7 = CutoffRule('Density', '><', [Q_(1.5, 'G/cc'), Q_(2.5, 'G/cc')])
rule8 = CutoffRule('Porosity', '==', Q_(0.3, ''))
rule9 = CutoffRule('Porosity', '<', Q_(0.35, 'dimensionless'))

log_table = {
    'P velocity': 'vp',
    'S velocity': 'vs',
    'Density': 'rhob',
    'Porosity': 'phie',
    'Volume': 'vcl'}

log_table_multi = {
    'P velocity': ['vp_virg', 'vp_brine', 'vp_oil', 'vp_gas'],
    'S velocity': ['vs_virg', 'vs_brine', 'vs_oil', 'vs_gas'],
    'Density': ['rhob_virg', 'rhob_brine', 'rhob_oil', 'rhob_gas']}

fm1 = StratUnit('Test1 FM', 1)
fm2 = StratUnit('Test2 FM', 1)
gp1 = StratUnit('Test1 GP', 2)
interval1 = Interval('TestWell', Q_(100., 'm'), Q_(200., 'm'), fm1)
interval2 = Interval('TestWell', Q_(200., 'm'), Q_(300., 'm'), fm2)
interval3 = Interval('TestWell', Q_(100., 'm'), Q_(300., 'm'), gp1)
interval4 = Interval('AnotherWell', Q_(100. - 10., 'm'), Q_(200. + 10., 'm'), fm1)
interval5 = Interval('AnotherWell', Q_(200. - 10., 'm'), Q_(300. + 10., 'm'), fm2)
interval6 = Interval('AnotherWell', Q_(100. - 10., 'm'), Q_(300. + 10., 'm'), gp1)

class CutoffTests(unittest.TestCase):
    def test_rule_init(self):
        limits = [Q_(4,'m'), [Q_(4,'m'), Q_(10,'m')], 'interval_name']
        for limit in limits:
            print(limit)
            rule = CutoffRule('test', '>', limit)
            self.assertIsInstance(rule, CutoffRule)
        rule = CutoffRule('', None, 'test_interval')
        self.assertIsInstance(rule, CutoffRule)

    def test_failed_rule_init(self):
        limits = [4.0, [4.0, 4.0], 11]
        for limit in limits:
            print(limit)
            self.assertRaises(IOError, CutoffRule, param='test', operator='>', limit=limit)
        self.assertRaises(IOError, CutoffRule, param='', operator=None, limit=4)
        self.assertRaises(IOError, CutoffRule, param='', operator='XXX', limit=4)

    def test_print_rules(self):
        for rule in [rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9]:
            print(rule)
        self.assertTrue(True)

    def test_from_string(self):
        for rule in [rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9]:
            new_rule = CutoffRule(from_string=str(rule))
            print(rule, new_rule)

        string = "VCL>0.8[], PHIE<0.1[], vp><[2000, 4000][m/s], interval:Heather FM[]"
        cutoffs = Cutoffs(from_string=string)
        print(cutoffs)
        self.assertTrue(True)

    def test_failed_init(self):
        cutoffs = Cutoffs
        self.assertRaises(TypeError, cutoffs, name='test', alpha='JA', beta='Nej' )

    def test_init(self):
        cutoffs = Cutoffs(cutoffs=[rule1, rule2])
        print(len(cutoffs))
        cutoffs.append([rule3, rule4])
        cutoffs.append(rule1)
        cutoffs.append([rule1])
        cutoffs.append(rule5)
        print(len(cutoffs))
        print(cutoffs.cutoff_params)
        print(cutoffs)
        print(cutoffs.get_dict())
        self.assertTrue(True)

    def test_classification_table(self):
        from bokeh.io import output_file
        from bokeh.plotting import column
        from blixt_geo_py.core.core import CutoffRule, ClassificationTable
        output_file(os.path.join(project_dir,'plot.html'))

        rule1 = CutoffRule('param1', '>', Q_(100, 'm'))
        rule2 = CutoffRule('param2', '<', Q_(10, 'm'))
        rule3 = CutoffRule('param3', '==', Q_(1000, 'm'))
        rule5 = CutoffRule('param5', '><', [Q_(10, 'm'), Q_(1000, 'm')])
        ct = ClassificationTable([rule1, rule2, rule3, rule5])
        # ct = ClassificationTable()
        rules_cds = ct.cds
        # print(ct.cds.data)
        # table, add_row, delete_row, update, use = ct.draw(rules_cds, ['log A', 'log B'], units=['m', 'km'])
        table, classification_controls = ct.draw(rules_cds)
        print(ct.active_cutoffs(rules_cds))
        rules_cds.data['use'] = [True, True, True, True]
        print(ct.active_cutoffs(rules_cds))

        show(column(table, classification_controls))
        self.assertTrue(True)

    def test_classification_mask(self):
        from bokeh.io import output_file
        from bokeh.plotting import column
        from blixt_geo_py.core.core import CutoffRule, ClassificationTable

        output_file(os.path.join(project_dir,'plot.html'))

        rule1 = CutoffRule('param1', '>', Q_(100, 'm'))
        rule2 = CutoffRule('param2', '<', Q_(10, 'm'))
        ct = ClassificationTable([rule1, rule2])
        rules_cds = ct.cds
        table, classification_controls = ct.draw(rules_cds, ['param1', 'param2'], units=['m', 'km'])

        data_cds = ColumnDataSource(dict(
            mask=np.ones(10, dtype=bool),
            param1=np.linspace(10, 200, 10),
            param2 = np.linspace(1, 12, 10)
        ))

        # Force the rules to be active as cutoffs
        rules_cds.data['use'] = [True, True]
        mask = ct.create_mask(rules_cds, data_cds)
        print('Both cutoff rules are active: ', mask)

        rules_cds.data['use'] = [True, False]
        mask = ct.create_mask(rules_cds, data_cds)
        print('First cutoff rules is active: ', mask)

        rules_cds.data['use'] = [False, True]
        mask = ct.create_mask(rules_cds, data_cds)
        print('Second cutoff rules is active: ', mask)

        show(column(table, classification_controls))
        self.assertTrue(True)

    def test_log_types(self):
        cutoffs = Cutoffs(cutoffs=[rule5, rule6, rule7])
        # rule5 can not be converted using the LogTable because it is not contained in it
        print(cutoffs.cutoff_params)
        new_cutoffs = cutoffs.use_log_table(LogTable(log_table))
        print(new_cutoffs.cutoff_params)

        # With a multi log LogTable the user is asked about the log types of the rules, and of no others
        with patch('builtins.input', side_effect=['1', '2']) as mock_input:
            new_cutoffs = cutoffs.use_log_table(LogTable(log_table_multi))
        self.assertEqual(['name5', 'vp_brine', 'rhob_oil'], new_cutoffs.cutoff_params)
        self.assertEqual(2, mock_input.call_count)

    def test_select_log(self):
        lt = LogTable(log_table_multi, name='My table')
        with patch('builtins.input', side_effect=['2']) as mock_input, patch('builtins.print') as mock_print:
            self.assertEqual('vp_oil', lt.select_log('P velocity'))
            # The answer is remembered
            self.assertEqual('vp_oil', lt.select_log('P velocity'))
        self.assertEqual(1, mock_input.call_count)
        # The user is shown the list of logs to choose from
        printed = [_call.args[0] for _call in mock_print.call_args_list]
        self.assertIn('P velocity in LogTable My table', printed[0])
        self.assertEqual(['  0: vp_virg', '  1: vp_brine', '  2: vp_oil', '  3: vp_gas'], printed[1:5])

        # A copy asks again
        with patch('builtins.input', side_effect=['0']):
            self.assertEqual('vp_virg', lt.copy().select_log('P velocity'))

        # Asks again until the answer is a valid index
        with patch('builtins.input', side_effect=['', 'vp_oil', '-1', '4', '1.5', ' 3 ']) as mock_input:
            self.assertEqual('rhob_gas', LogTable(log_table_multi).select_log('Density'))
        self.assertEqual(6, mock_input.call_count)

        # There is nothing to ask when there is only one log
        with patch('builtins.input') as mock_input:
            lt = LogTable({'Density': 'rhob', 'Resistivity': ['rdep', 'rmed']})
            self.assertEqual('rhob', lt.select_log('Density'))
            self.assertEqual('vp', LogTable(log_table).select_log('P velocity'))
        mock_input.assert_not_called()

        self.assertRaises(KeyError, LogTable(log_table_multi).select_log, 'Volume')
        self.assertRaises(ValueError, LogTable({'Density': []}).select_log, 'Density')

        # Without user input, e.g. when run as a batch job, it fails with an explanation
        with patch('builtins.input', side_effect=EOFError):
            with self.assertRaisesRegex(IOError, 'vp_virg, vp_brine, vp_oil, vp_gas'):
                LogTable(log_table_multi).select_log('P velocity')

    def test_single_log(self):
        lt = LogTable(log_table)
        self.assertIs(lt, lt.single_log())

        lt = LogTable(log_table_multi, name='My table')
        with patch('builtins.input', side_effect=['3', '0']) as mock_input:
            single = lt.single_log(['P velocity', 'Density', 'Volume'])
        self.assertEqual({'P velocity': 'vp_gas', 'Density': 'rhob_virg'}, single.dict)
        self.assertFalse(single.multi_log)
        self.assertEqual('My table', single.name)
        self.assertEqual(2, mock_input.call_count)
        # The original is unchanged
        self.assertEqual(log_table_multi['Density'], lt['Density'])

        # Asks only about the log type that hasn't been answered, and gives the same answers as the cutoffs get
        with patch('builtins.input', side_effect=['1']) as mock_input:
            single = lt.single_log()
        self.assertEqual({'P velocity': 'vp_gas', 'S velocity': 'vs_brine', 'Density': 'rhob_virg'}, single.dict)
        self.assertEqual(1, mock_input.call_count)
        self.assertEqual(['vp_gas'], Cutoffs(cutoffs=[rule6]).use_log_table(lt).cutoff_params)

        # A deepcopy keeps the answers
        with patch('builtins.input') as mock_input:
            self.assertEqual('vp_gas', deepcopy(lt).select_log('P velocity'))
        mock_input.assert_not_called()

    def test_create_mask_from_cutoff_rule(self):
        data = {'name2': np.linspace(5., 20, 10)}
        mask = rule2.create_mask(data)
        print(mask)
        self.assertTrue(
            all(_x == _y for _x, _y in zip(mask, [True, True, True, False, False, False, False, False, False, False])))

    def test_create_mask_from_cutoffs(self):
        data_no_units = {'name1': np.linspace(90., 190, 10), 'name2': np.linspace(5., 20, 10)}
        data_with_units = {'name1': Q_(np.linspace(90., 190, 10), 'm'), 'name2': Q_(np.linspace(5., 20, 10), 'm')}
        cfs = Cutoffs(cutoffs=[rule1, rule2])
        mask = cfs.create_mask(data_with_units)
        print(mask)
        self.assertTrue(
            all(_x == _y for _x, _y in zip(mask, [False, True, True, False, False, False, False, False, False, False])))

class LogTableTests(unittest.TestCase):
    def test_lt_init(self):
        lt = LogTable( log_table)
        for _key in list(lt.keys()):
            print('{}: {}'.format(_key, lt[_key]))
        lt.test = 'A log name'  # this has no function now
        lt['TEST'] = 'A log name' # But this work when __setitem__ is kept untouched
        print(lt.keys())
        inv = lt.invert
        print(lt.log_names)
        print(lt.log_types)
        print(inv)
        print(lt.dict)
        print(lt['P velocity'])

    def test_from_invert(self):
        inv_dict = {'bs': 'Bit size', 'cali': 'Caliper', 'cpi_phie': 'Porosity', 'cpi_sw': 'Saturation', 'gr': 'Gamma ray', 'rho_fsub_gas80': 'Density', 'rho_fsub_oil80': 'Density', 'rho_insitu_conditioned': 'Density', 'vcl_used': 'Volume', 'vp_fsub_gas80': 'P velocity', 'vp_fsub_oil80': 'P velocity', 'vp_insitu_conditioned': 'P velocity', 'vs_fsub_gas80': 'S velocity', 'vs_fsub_oil80': 'S velocity', 'vs_insitu_conditioned': 'S velocity', 'vsh_mineral': 'Volume'}
        lt = LogTable()
        lt.from_invert(inv_dict)
        print(lt.log_types)
        print(lt.log_names)
        print(lt['Bit size'])

    def test_multi(self):
        lt = LogTable(log_table_multi)
        print(list(lt.keys()))
        lt['Density'].append('my other rhob')
        print(lt.log_names)
        print(lt.log_types)
        print(lt.invert)
        print(lt.dict)

    def test_mixing(self):
        # A table that mixes single log names and lists is a multi log table, where all values are lists. Both
        # orders must give the same result, as multi_log does not depend on which log type comes first
        for _table in ({'Density': 'RHOB', 'Resistivity': ['rdep', 'RMED']},
                       {'Resistivity': ['rdep', 'RMED'], 'Density': 'RHOB'}):
            lt = LogTable(_table)
            with self.subTest(first=list(_table.keys())[0]):
                self.assertTrue(lt.multi_log)
                self.assertEqual(['rhob'], lt['Density'])
                self.assertEqual(['rdep', 'rmed'], lt['Resistivity'])
                self.assertEqual(sorted(['rhob', 'rdep', 'rmed']), sorted(lt.log_names))
                self.assertEqual({'rhob': 'Density', 'rdep': 'Resistivity', 'rmed': 'Resistivity'}, lt.invert)

    def test_single_log_name_into_multi(self):
        # A single log name added to a multi log table is stored as a list with one log name
        lt = LogTable(log_table_multi)
        lt['Porosity'] = 'PHIE'
        self.assertTrue(lt.multi_log)
        self.assertEqual(['phie'], lt['Porosity'])
        self.assertEqual('Porosity', lt.invert['phie'])

    def test_list_into_single(self):
        # A list of log names added to a normal table turns it into a multi log table, where the existing log names
        # are turned into lists
        lt = LogTable(log_table)
        self.assertFalse(lt.multi_log)
        lt['Resistivity'] = ['RDEP', 'rmed']
        self.assertTrue(lt.multi_log)
        self.assertEqual(['rdep', 'rmed'], lt['Resistivity'])
        for _key, _value in log_table.items():
            self.assertEqual([_value], lt[_key], _key)

    def test_lowercase(self):
        # Log names are stored in lowercase letters, also when added after the table is created
        lt = LogTable({'P velocity': 'VP'})
        lt['S velocity'] = 'VS'
        lt.update({'Density': 'RHOB'})
        lt.setdefault('Porosity', 'PHIE')
        self.assertEqual({'P velocity': 'vp', 'S velocity': 'vs', 'Density': 'rhob', 'Porosity': 'phie'}, dict(lt))

    def test_input_not_modified(self):
        # The dictionary used to create the table is left untouched
        _table = {'P velocity': 'VP', 'Resistivity': ['RDEP']}
        LogTable(_table)
        self.assertEqual({'P velocity': 'VP', 'Resistivity': ['RDEP']}, _table)

    def test_invalid_log_name(self):
        with self.assertRaises(TypeError):
            LogTable({'P velocity': 1})
        with self.assertRaises(TypeError):
            LogTable({'P velocity': ['vp', None]})

    def test_copies(self):
        # Copies are LogTables with the same content, multi_log and name
        import copy
        import pickle
        for _table in (log_table, log_table_multi):
            lt = LogTable(_table, name='My table')
            for _how, _copy in (('copy', lt.copy()), ('deepcopy', copy.deepcopy(lt)),
                                ('pickle', pickle.loads(pickle.dumps(lt)))):
                with self.subTest(how=_how, multi_log=lt.multi_log):
                    self.assertIsInstance(_copy, LogTable)
                    self.assertEqual(dict(lt), dict(_copy))
                    self.assertEqual(lt.multi_log, _copy.multi_log)
                    self.assertEqual('My table', _copy.name)

    def test_from_invert_into_existing(self):
        # from_invert() on a table with single log names turns all values into lists
        lt = LogTable({'Porosity': 'phie'})
        lt.from_invert({'vp_dry': 'P velocity', 'vp_gas': 'P velocity'})
        self.assertTrue(lt.multi_log)
        self.assertEqual({'Porosity': ['phie'], 'P velocity': ['vp_dry', 'vp_gas']}, dict(lt))

    # def test_un_translate(self):
    #     lt1 = LogTable(log_table)
    #     rename_logs = {'phie': ['cpi_phie', 'xxx_phie']}
    #     lt2 = lt1.un_translate(rename_logs=rename_logs)
    #     print(lt2.log_names)

    #     print('Using a multi_log LogTable:')
    #     lt1 = LogTable(log_table_multi)
    #     rename_logs = {'vp_virg': ['vp_dry', 'vp_insitu']}
    #     lt2 = lt1.un_translate(rename_logs=rename_logs)
    #     print(lt2.log_names)

    def test_keep(self):
        lt1 = LogTable(log_table)
        keep = ['vp', 'rhob']
        lt2 = lt1.keep(keep)
        print(lt2.log_types)
        print(lt2.log_names)

        lt1 = LogTable(log_table_multi)
        keep = ['vp_brine', 'vp_oil', 'rhob_virg']
        lt2 = lt1.keep(keep)
        print(lt2)


class TemplateTestCase(unittest.TestCase):

    def test_from_scratch(self):
        t = Template(**{'name': 'MY NAME', 'well': 'MY WELL', 'units': 'METER'})
        print(list(t.keys()))
        print(t.name, t.units, t.well)
        t = Template()
        print(t)

    def test_from_project_table(self):
        t = Template()
        t.get_from_project(project_table, 'Resistivity')
        t.max = 999
        t.colormap = 'A GIANT COLOR'
        print(t)
        d = t.__dict__
        print(type(t), type(d))

    def test_dictionary_from_project_table(self):
        table = pd.read_excel(project_table, header=1, sheet_name='Templates', engine='openpyxl')
        template_dict = templates_from_table(table)
        for i, _key in enumerate(list(template_dict.keys())):
            print(_key)
            if i == 0:
                print(template_dict[_key])

        table = pd.read_excel(project_table, header=1, sheet_name='Well settings', engine='openpyxl')
        template_dict = templates_from_table(table, well_style=True)
        for i, _key in enumerate(list(template_dict.keys())):
            print(_key)
            if i == 0:
                print(template_dict[_key])

    def test_from_project_table_error(self):
        t = Template()
        # t.get_from_project(project_table, 'XXX')
        self.assertRaises(KeyError, t.get_from_project, project_file=project_table, log_type='XXX')

    def test_templates_table(self):
        from blixt_geo_py.core.core import TemplatesTable
        from bokeh.io import output_file
        output_file(os.path.join(test_file_dir,'plot.html'))

        templates = []
        for log_type in ['Resistivity', 'P velocity', 'S velocity']:
            t = Template()
            t.get_from_project(project_table, log_type)
            t.name = log_type  # The original template has no name
            templates.append(t)
        print(templates)
        tmpl_table = TemplatesTable(templates)
        print(tmpl_table.templates)
        for _t in tmpl_table.templates:
            print(_t.name)
        tmpl_cds = tmpl_table.cds
        print(tmpl_cds.data)
        table = tmpl_table.draw(tmpl_cds)
        show(table)


class IntervalTests(unittest.TestCase):

    def test_create_intervals(self):
        wis = Intervals('TEST', [interval1, interval2, interval3, interval4, interval5, interval6])

        print(wis)
        print('-x1-')
        print(wis.well_names())
        print('-x2-')
        print(wis.interval_names())
        print('-x3-')
        print(wis.get_well_depth_range('TestWell'))
        print('-x4-')
        print(wis.get_well_depth_range('AnotherWell'))
        print('-x5-')
        _i = wis.get_interval('Test1 FM', 'TestWell')
        print(_i.thickness)
        print('-x6-')
        print(_i.mid)
        print('-x7-')
        print(_i.distance_to_top(Q_(0, 'm')))
        print('-x8-')

        self.assertIsInstance(wis, Intervals)

    def test_read(self):
        f = "C:\\Users\\marten.blixt\\OneDrive - Petrolia NOCO AS\\Technical work\\Sodir_well_tops_BarentsSea.xlsx"
        wis = Intervals(name='Working intervals')
        wis.read_sodir_tops(f)

        # Test removing most well
        wis.keep_wells(['7016_2_1', '7119_7_1'])

        for well in wis.well_names():
            print('Well: {}'.format(well))
            print(' depths: {}'.format(wis.get_well_depth_range(well)))
            print(' Number of intervals: {}'.format(len(wis.get_well_intervals(well))))
            for _interval in wis.get_well_intervals(well):
                print('  Interval: {}: {} - {}'.format(_interval.name, _interval.top.magnitude,
                                                       _interval.base.magnitude))
        print(wis.interval_names())

        # fig, axs = plt.subplots(ncols=2)
        # wis.get_well('7119_7_1').plot_intervals(3, axs[0])
        # wis.get_well('7119_7_1').plot_intervals(2, axs[1], depth_range=(3000., 3800.))
        # plt.show()

        # out_file = os.path.join(project_dir, 'test.xlsx')
        # test = wis.write_to_excel(out_file, 'Working intervals', 'Interval info',
        #                           append=False)
        # print(test)

        self.assertIsInstance(wis, Intervals)

    def test_read_project_intervals(self):
        project_file = os.path.join(project_dir,"blixt_geo_py\\excels\\project_table.xlsx")
        wis = Intervals()
        wis.read_blixt_tops(project_file)
        # print(wis)
        # for _i in wis.intervals:
        #     print(_i)
        print(wis.get_strat_units())
        print(wis.get_intervals_dict('Well_F'))
        for well in ['Well_A', 'Well_B', 'Well_C', 'Well_F', 'Well_l']:
            print(well)
            print([_i.name for _i in wis.get_well_intervals(well)])

    def test_well_intervals(self):
        wis = Intervals(
            name='MyIntervals',
            intervals=[
                Interval('Well A', Q_(2300., 'm'), Q_(2500., 'm'), interval_info=StratUnit('Interval A', 2)),
                Interval('Well A', Q_(2700., 'm'), Q_(3000., 'm'), interval_info=StratUnit('Interval C', 2)),
                Interval('Well A', Q_(2500., 'm'), Q_(2700., 'm'), interval_info=StratUnit('Interval B', 2)),
                Interval('Well A', Q_(2500., 'm'), Q_(3000., 'm'), interval_info=StratUnit('Group A', 1))
            ]
        )
        print([_int.name for _int in wis.get_well_intervals('Well A')])
        print([_int.name for _int in wis.get_well_intervals('Well A', sorted_by_top=True)])
        wis.keep_intervals(['Interval {}'.format(_x) for _x in ['A', 'B', 'C'] ])
        print([_int.name for _int in wis.get_well_intervals('Well A')])
        print([_int.name for _int in wis.get_well_intervals('Well A', sorted_by_top=True)])


    def test_cutoff_rule(self):
        from blixt_geo_py.utils.masks import create_mask
        project_file = os.path.join(project_dir,"blixt_geo_py\\excels\\project_table.xlsx")
        wis = Intervals()
        wis.read_blixt_tops(project_file)
        _rule1 = wis.get_cutoff_rule('Shale C', 'WELL_F')
        _rule2 = wis.get_cutoff_rule('NO INTERVAL', 'WELL_F')
        print(_rule1, _rule2)
        md = Q_(np.linspace(1000., 3000., 20), 'm')
        for _rule in [_rule1, _rule2]:
            mask = create_mask(md, _rule.operator, _rule.limit)
            print(md[mask])


    def test_append(self):
        append_file = os.path.join(project_dir, 'blixt_geo_py\\results_folder\\test.xlsx')
        wis = Intervals(name='TEST', intervals=[interval1, interval2])
        wis.add_interval(interval3)

        #wis.read_blixt_tops(append_file)

        print(wis)
        self.assertIsInstance(wis, Intervals)


    def test_intervals_table(self):
        from blixt_geo_py.core.core import Intervals, WorkingIntervalsTable
        from bokeh.io import output_file
        output_file(os.path.join(test_file_dir,'plot.html'))
        wis = Intervals()
        wis.read_blixt_tops(project_table)
        wis.keep_wells(['WELL_B', 'WELL_C', 'WELL_F'])
        wis_table = WorkingIntervalsTable(wis)
        wis_cds = wis_table.cds
        print(wis_cds.data['use'])
        print('-x1-')
        print(wis_table.active_intervals_dict(wis_cds))
        print(wis_table.active_intervals(wis_cds))
        # Modify Column Data Source
        for i in range(len(wis_cds.data['use'])):
            wis_cds.data['use'][i] = False
        # Add it back to wis_tabl
        wis_table.cds = wis_cds
        # Read it out again
        wis_cds = wis_table.cds
        print(wis_table.active_intervals(wis_cds))

        table = wis_table.draw(wis_table.cds)
        show(table)

    def test_intervals_table_2(self):
        from blixt_geo_py.core.core import Intervals, WorkingIntervalsTable
        wis = Intervals(
            name='test', intervals=[
                Interval( well='one', top=Q_(1050, 'm'), base=Q_(1150, 'm'), interval_info=StratUnit('wi_1', 1)),
                Interval( well='one', top=Q_(1200, 'm'), base=Q_(1400, 'm'), interval_info=StratUnit('wi_2', 1)),
                Interval( well='two', top=Q_(1550, 'm'), base=Q_(1650, 'm'), interval_info=StratUnit('wi_1', 1)),
                Interval( well='two', top=Q_(1800, 'm'), base=Q_(1950, 'm'), interval_info=StratUnit('wi_2', 1))
            ] )
        wis_table = WorkingIntervalsTable(wis)
        wis_cds = wis_table.cds
        mask = wis_table.create_mask(wis_cds, md=Q_(np.linspace(1000., 2000., 10), 'm'),
                                     wells=None)
        self.assertTrue(np.array_equal(mask, np.array([0, 1, 1, 1, 0, 1, 0, 0, 1, 0], dtype=bool)))
        print('-x1-')
        mask = wis_table.create_mask(wis_cds, md=Q_(np.linspace(1000., 2000., 10), 'm'),
                                     wells=['one'] * 10)
        self.assertTrue(np.array_equal(mask, np.array([0, 1, 1, 1, 0, 0, 0, 0, 0, 0], dtype=bool)))
        print('-x2-')
        mask = wis_table.create_mask(wis_cds, md=Q_(np.linspace(1000., 2000., 10), 'm'),
                                     wells=['two'] * 10)
        self.assertTrue(np.array_equal(mask, np.array([0, 0, 0, 0, 0, 1, 0, 0, 1, 0], dtype=bool)))

    def test_overlapping_intervals(self):
        project_file = os.path.join(project_dir,"blixt_geo_py\\excels\\project_table.xlsx")
        wis = Intervals()
        wis.read_blixt_tops(project_file)

        overlaps = wis.check_for_overlapping_intervals()
        print(overlaps)
        overlaps = wis.check_for_overlapping_intervals('well_f')
        print(overlaps)
        overlaps = wis.check_for_overlapping_intervals('WELL_A')
        print(overlaps)


class HeaderTestCase(unittest.TestCase):

    def test_Header(self):
        import time
        h = Header({'name': 'MY NAME', 'well': 'MY WELL'})
        print(list(h.keys()))
        print(h.name, h.creation_date)
        time.sleep(1)
        h.orig_filename = 'A TEST'
        print(h.orig_filename, h.creation_date, h.modification_date)
        print(h)
        print(list(h.keys()))
        self.assertTrue(all([_key in ['name', 'well', 'creation_info', 'creation_date', 'orig_filename', 'modification_date', 'modification_history', 'note', 'log_type'] for _key in list(h.keys())]))


class LithoFluidTests(unittest.TestCase):

    def litho_fluids(self):
        """
        Create a set of useful litho-fluids
        :return:
        """
        from blixt_geo_py.core.core import LithoFluid
        lf1 = LithoFluid(None, 3440., 2170., 2.17)
        lf2 = LithoFluid('Oseberg SST', 3400., 2050., 2.21)
        lf3 = LithoFluid('Fluid sub. problem', 3200., 2050., 2.21)

        return lf1, lf2, lf3

    def test_get_litho_fluids(self):
        from blixt_geo_py.core.core import LithoFluids
        lf1, lf2, lf3 = self.litho_fluids()
        lfs = LithoFluids([lf1, lf2, lf3])
        print(lfs['Oseberg SST'])
        print([_lf.name for _lf in lfs.litho_fluids])

    def test_fluid_sub(self):
        for lf in self.litho_fluids():
            lf_hc = lf.fluid_sub(verbose=True)
            # print(lf_hc.name, lf_hc.vp.magnitude, lf_hc.vs.magnitude, lf_hc.rho.magnitude)
        # In RokDoc we have the following results for these values:
        #  lf1 -> 80% oil: 3311.	2194.	2.12
        #  lf1 -> 100% gas: 3274.	2305.	1.92
        #  lf2 -> 80% oil: 3269.	2070.	2.17
        #  lf3 -> 80% oil: Fails because of K_dry
        lf = self.litho_fluids()[0]
        lf_gas = lf.fluid_sub(s_w2=Q_(0., ''), hc=dict(rho=Q_(0.15, 'G/cc'), k=Q_(0.037, 'GPa')), verbose=True)
        # print('Gas: ', lf_gas.name, lf_gas.vp.magnitude, lf_gas.vs.magnitude, lf_gas.rho.magnitude)
        lf_heavy_oil = lf.fluid_sub(hc=dict(rho=Q_(1.1, 'G/cc'), k=Q_(2.757, 'GPa')), verbose=True)
        # print('Heavy oil: ', lf_heavy_oil.name, lf_heavy_oil.vp.magnitude, lf_heavy_oil.vs.magnitude, lf_heavy_oil.rho.magnitude)


    def test_2d_lf(self):
        from blixt_geo_py.core.core import LithoFluid
        def vp(_i):
            return Q_(3000. +  5. * _i, 'm/s')
        def vs(_i):
            return Q_(1500. +  5. * _i, 'm/s')
        def rho(_i):
            return Q_(2.5 +  0.1 * _i, 'grams/cm^3')

        lf = LithoFluid(vp=vp, vs=vs, rho=rho,
                        vp_std_dev=1., vs_std_dev=1., rho_std_dev=0.01,
                        vp_vs_cc=0.9, vp_rho_cc=0.9, vs_rho_cc=0.9)
        print(lf.vp(10))
        print(lf.to_sums_dict(10))
        self.assertEqual(3050., lf.vp(10).magnitude)

    def test_plot(self):
        from blixt_geo_py.core.core import LithoFluid
        from matplotlib.patches import Ellipse
        lf = LithoFluid()
        fig, ax = plt.subplots()
        lf.plot(ax=ax)
        # The data points, and the ellipses of one and two standard deviations
        self.assertEqual(1, len(ax.collections))
        self.assertEqual(2, len([_p for _p in ax.patches if isinstance(_p, Ellipse)]))
        self.assertEqual('AI [g/cc m/s]', ax.get_xlabel())
        show_or_close()

    def test_plot_label(self):
        from blixt_geo_py.core.core import LithoFluid
        fig, ax = plt.subplots()
        # The name is the default label
        LithoFluid(default='shale').plot(ax=ax)
        LithoFluid(default='brine_sst').plot(ax=ax, label='Brine sand', color='r')
        self.assertEqual(['shale', 'Brine sand'], [_t.get_text() for _t in ax.get_legend().get_texts()])
        show_or_close()

    def test_plot_shared_axes(self):
        """
        All litho fluids plotted in the same axes must be within the limits, not only the first
        """
        from blixt_geo_py.core.core import LithoFluid
        fig, ax = plt.subplots()
        LithoFluid(default='shale').plot(ax=ax)
        LithoFluid(default='gas_sst').plot(ax=ax, color='r')
        fig.canvas.draw()
        for _points in ax.collections:
            x, y = _points.get_offsets().T
            self.assertLessEqual(ax.get_xlim()[0], np.min(x))
            self.assertGreaterEqual(ax.get_xlim()[1], np.max(x))
            self.assertLessEqual(ax.get_ylim()[0], np.min(y))
            self.assertGreaterEqual(ax.get_ylim()[1], np.max(y))
        show_or_close()

    def test_crossplot_limits(self):
        """
        Limits in the templates must be used, also when another plot is added to the same axes
        """
        from blixt_geo_py.plotting import crossplot as xp
        fig, ax = plt.subplots()
        xp.plot(np.array([1., 2.]), np.array([1., 2.]), cdata='b', cbar=False, ax=ax,
                xtempl={'min': 0., 'max': 5.}, ytempl={'min': -1., 'max': 3.})
        xp.plot(np.array([10., 20.]), np.array([10., 20.]), cdata='r', cbar=False, ax=ax,
                xtempl={'min': 0., 'max': 5.}, ytempl={'min': -1., 'max': 3.})
        self.assertEqual((0., 5.), ax.get_xlim())
        self.assertEqual((-1., 3.), ax.get_ylim())
        show_or_close()

    def test_table_save(self):
        """
        Click the Save button of the table, with the file dialog replaced by the name of a temporary file
        """
        import tempfile
        from unittest import mock
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable
        from blixt_geo_py.io.io import read_sums_and_averages

        lfs = LithoFluids(litho_fluids=[LithoFluid(default='shale'), LithoFluid(default='brine_sst')])
        lft = LithoFluidsTable(lfs)
        _, lf_controls = lft.draw(lft.cds)
        save = [_b for _b in lf_controls.children if _b.label == 'Save'][0]

        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            with mock.patch('blixt_geo_py.core.core.save_file', return_value=file_name):
                for _callback in save._event_callbacks['button_click']:
                    _callback()
            data = read_sums_and_averages(file_name)

        self.assertEqual({'shale', 'brine_sst'}, set(data.keys()))
        self.assertEqual(3445, data['shale']['VpMean'])
        self.assertEqual(260, data['brine_sst']['VpStdDev'])
        self.assertEqual(0.92, data['brine_sst']['VpVsCorrCoef'])

    @staticmethod
    def click(button):
        for _callback in button._event_callbacks['button_click']:
            _callback()

    def fluid_sub_table(self, advanced=False):
        """
        Returns a table with a brine sand and a shale, its cds, and its button and dialog of the fluid substitution
        """
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable
        lfs = LithoFluids([LithoFluid(default='brine_sst'), LithoFluid(default='shale')])
        lft = LithoFluidsTable(lfs, advanced=advanced)
        cds = lft.cds
        _, controls = lft.draw(cds)
        return lfs, cds, controls.children[-1], controls.elements[0]

    def apply_button(self, dialog):
        from bokeh.models import Button
        return [_b for _b in dialog.select({'type': Button}) if _b.label == 'Apply'][0]

    def test_fluid_sub_defaults_come_from_definitions(self):
        from unittest.mock import patch
        from blixt_geo_py.core.core import LithoFluid
        from blixt_geo_py.utils.definitions import default_fluids, default_minerals
        lf = LithoFluid(default='brine_sst')
        hc, mineral, brine = default_fluids['rich gas'], default_minerals['calcite'], dict(default_fluids['brine'])
        brine['k'] = Q_(3., 'GPa')
        expected = lf.fluid_sub(hc=hc, mineral=mineral, brine=brine)

        with patch.dict(default_fluids, {'oil': hc, 'brine': brine}), patch.dict(default_minerals, {'quartz': mineral}):
            result = lf.fluid_sub()

        for _key in ['vp', 'vs', 'rho']:
            self.assertEqual(getattr(expected, _key), getattr(result, _key))

    def test_fluid_sub_with_negative_porosity_does_nothing(self):
        from blixt_geo_py.core.core import LithoFluid
        from blixt_geo_py.utils.definitions import default_minerals
        lf = LithoFluid(default='brine_sst')  # Its density of 2.4 G/cc is higher than the 1.8 G/cc of the ooze

        with self.assertLogs('blixt_geo_py.core.core', level='WARNING') as logs:
            result = lf.fluid_sub(mineral=default_minerals['ooze'])
        self.assert_is_unchanged_copy(lf, result)
        self.assertIn('negative', logs.output[0])
        self.assertIn('denser than the mineral', logs.output[0])

        with self.assertLogs('blixt_geo_py.core.core', level='WARNING') as logs:
            result = lf.fluid_sub(phi=Q_(-0.1, ''))
        self.assert_is_unchanged_copy(lf, result)
        self.assertIn('The given porosity is negative', logs.output[0])

        # It is a new LithoFluid, so changing it leaves the original as it was
        result.name = 'changed'
        self.assertEqual('brine_sst', lf.name)

    def assert_is_unchanged_copy(self, lf, result):
        self.assertIsNot(lf, result)
        self.assertEqual(lf.name, result.name)
        for _key in ['vp', 'vs', 'rho', 'vp_std_dev', 'vs_std_dev', 'rho_std_dev']:
            self.assertEqual(getattr(lf, _key), getattr(result, _key))

    def test_fluid_sub_with_positive_porosity_gives_no_warning(self):
        from blixt_geo_py.core.core import LithoFluid
        lf = LithoFluid(default='brine_sst')
        with self.assertNoLogs('blixt_geo_py.core.core', level='WARNING'):
            result = lf.fluid_sub()
        self.assertIsNot(lf, result)
        self.assertEqual('brine_sst_hc', result.name)

    def test_fluid_sub_dialog_refuses_a_negative_porosity(self):
        from bokeh.models import Div, Select
        _, cds, button, dialog = self.fluid_sub_table()
        before = {_k: list(_v) for _k, _v in cds.data.items()}
        cds.selected.indices = [0]
        self.click(button)
        [_s for _s in dialog.select({'type': Select}) if _s.title == 'Mineral'][0].value = 'ooze'

        self.click(self.apply_button(dialog))

        self.assertTrue(dialog.visible)
        self.assertEqual(before, {_k: list(_v) for _k, _v in cds.data.items()})
        self.assertTrue(any('negative porosity' in str(_d.text) for _d in dialog.select({'type': Div})))

    def test_fluid_sub_adds_a_new_row(self):
        from blixt_geo_py.core.core import LithoFluid
        lfs, cds, button, dialog = self.fluid_sub_table()
        original = LithoFluid(default='brine_sst')
        expected = original.fluid_sub()
        cds.selected.indices = [0]

        self.click(button)
        self.assertTrue(dialog.visible)
        self.click(self.apply_button(dialog))
        self.assertFalse(dialog.visible)

        # The dialog starts with the default values of fluid_sub(). The new row comes last, and the others are unchanged
        self.assertEqual(['brine_sst', 'shale', 'brine_sst_hc'], cds.data['name'])
        for _key, _old, _new, _other in (('vp', original.vp, expected.vp, 3445), ('vs', original.vs, expected.vs, 1767),
                                         ('rho', original.rho, expected.rho, 2.6)):
            self.assertEqual(_old.magnitude, cds.data[_key][0])
            self.assertEqual(_other, cds.data[_key][1])
            self.assertAlmostEqual(_new.magnitude, cds.data[_key][2])
        # The LithoFluids of the table has the new litho fluid too
        self.assertEqual(['brine_sst', 'shale', 'brine_sst_hc'], [_lf.name for _lf in lfs.litho_fluids])
        self.assertAlmostEqual(expected.vp.magnitude, lfs['brine_sst_hc'].vp.magnitude)

    @staticmethod
    def name_input(dialog):
        from bokeh.models import TextInput
        return list(dialog.select({'type': TextInput}))[0]

    def test_fluid_sub_name_of_the_new_litho_fluid(self):
        from bokeh.models import Div
        lfs, cds, button, dialog = self.fluid_sub_table()
        name = self.name_input(dialog)

        # The default name follows the selected row
        cds.selected.indices = [0]
        self.click(button)
        self.assertEqual('brine_sst_hc', name.value)
        cds.selected.indices = [1]
        self.assertEqual('shale_hc', name.value)
        cds.selected.indices = [0]

        name.value = ' My oil sand '
        self.click(self.apply_button(dialog))
        self.assertFalse(dialog.visible)
        self.assertEqual(['brine_sst', 'shale', 'My oil sand'], cds.data['name'])
        self.assertEqual('My oil sand', lfs.litho_fluids[2].name)

        def assert_refused(new_name, text):
            before = list(cds.data['name'])
            name.value = new_name
            self.click(self.apply_button(dialog))
            self.assertTrue(dialog.visible, new_name)
            self.assertEqual(before, cds.data['name'])
            self.assertTrue(any(text in str(_d.text) for _d in dialog.select({'type': Div})), text)

        # The same row can be substituted again, but it needs a name that isn't taken
        self.click(button)
        self.assertEqual('brine_sst_hc', name.value)
        assert_refused('  ', 'must have a name')
        assert_refused('BRINE_SST', 'already')
        assert_refused('my OIL sand', 'already')

        name.value = 'brine_sst_hc'
        self.click(self.apply_button(dialog))
        self.assertEqual(['brine_sst', 'shale', 'My oil sand', 'brine_sst_hc'], cds.data['name'])

    def test_fluid_sub_keeps_the_quasi_2d_litho_fluids(self):
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable

        def vp(_i):
            return Q_(3000. + _i, 'm/s')
        lfs = LithoFluids([LithoFluid(default='brine_sst'), LithoFluid(name='Quasi 2D', vp=vp)])
        lft = LithoFluidsTable(lfs, advanced=False)
        cds = lft.cds
        _, controls = lft.draw(cds)
        cds.selected.indices = [0]
        self.click(controls.children[-1])
        self.click(self.apply_button(controls.elements[0]))

        self.assertEqual(['brine_sst', 'Quasi 2D', 'brine_sst_hc'], [_lf.name for _lf in lfs.litho_fluids])
        self.assertIs(vp, lfs['Quasi 2D'].vp)
        self.assertNotIsInstance(lfs['brine_sst_hc'].vp, type(vp))

    def test_fluid_sub_uses_the_inputs(self):
        from bokeh.models import Select, Spinner
        from blixt_geo_py.core.core import LithoFluid
        from blixt_geo_py.utils.definitions import default_fluids, default_minerals
        expected = LithoFluid(default='brine_sst').fluid_sub(
            Q_(0.9, ''), Q_(0., ''), default_fluids['rich gas'], default_minerals['calcite'])

        _, cds, button, dialog = self.fluid_sub_table()
        cds.selected.indices = [0]
        self.click(button)
        values = {'Initial water saturation': 0.9, 'Final water saturation': 0., 'Hydrocarbon': 'rich gas',
                  'Mineral': 'calcite'}
        widgets = list(dialog.select({'type': Spinner})) + list(dialog.select({'type': Select}))
        self.assertEqual(set(values), {_w.title for _w in widgets})
        for _widget in widgets:
            _widget.value = values[_widget.title]
        self.click(self.apply_button(dialog))
        self.assertAlmostEqual(expected.vp.magnitude, cds.data['vp'][2])
        self.assertAlmostEqual(expected.vs.magnitude, cds.data['vs'][2])
        self.assertAlmostEqual(expected.rho.magnitude, cds.data['rho'][2])

    def test_fluid_sub_lists_the_default_hydrocarbons_and_minerals(self):
        from bokeh.models import Select
        from blixt_geo_py.utils.definitions import default_fluids, default_minerals
        _, _, _, dialog = self.fluid_sub_table()
        selects = {_s.title: _s for _s in dialog.select({'type': Select})}

        self.assertEqual('oil', selects['Hydrocarbon'].value)
        self.assertEqual(set(default_fluids) - {'brine'}, set(selects['Hydrocarbon'].options))
        self.assertEqual('quartz', selects['Mineral'].value)
        self.assertEqual(set(default_minerals), set(selects['Mineral'].options))

    def test_fluid_sub_needs_one_selected_row(self):
        _, cds, button, dialog = self.fluid_sub_table()
        before = {_k: list(_v) for _k, _v in cds.data.items()}
        for _indices in ([], [0, 1]):
            cds.selected.indices = _indices
            self.click(button)
            self.assertFalse(dialog.visible, _indices)

        # The selection can change while the dialog is open
        cds.selected.indices = [0]
        self.click(button)
        cds.selected.indices = [0, 1]
        self.click(self.apply_button(dialog))
        self.assertTrue(dialog.visible)
        self.assertEqual(before, {_k: list(_v) for _k, _v in cds.data.items()})

    def test_fluid_sub_copies_the_rest_of_the_row(self):
        lfs, cds, button, dialog = self.fluid_sub_table(advanced=True)
        cds.selected.indices = [0]
        self.click(button)
        self.click(self.apply_button(dialog))
        self.assertEqual('brine_sst_hc', cds.data['name'][2])
        self.assertEqual(260, cds.data['vp_std_dev'][2])
        self.assertEqual(0.62, cds.data['vp_rho_cc'][2])
        self.assertEqual(260, cds.data['vp_std_dev'][0])
        self.assertEqual(260, lfs['brine_sst_hc'].vp_std_dev.magnitude)
        self.assertEqual(0.62, lfs['brine_sst_hc'].vp_rho_cc.magnitude)

    def test_fluid_sub_failures_leave_the_table(self):
        from bokeh.models import Div
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable
        from blixt_geo_py.utils.definitions import default_minerals

        def assert_refused(cds, dialog, text):
            before = {_k: list(_v) for _k, _v in cds.data.items()}
            self.click(self.apply_button(dialog))
            self.assertTrue(dialog.visible)
            self.assertEqual(before, {_k: list(_v) for _k, _v in cds.data.items()})
            self.assertTrue(any(text in str(_d.text) for _d in dialog.select({'type': Div})), text)

        # A density that is the same as the default density of the mineral gives zero porosity
        lft = LithoFluidsTable(LithoFluids([LithoFluid(name='No pores', rho=default_minerals['quartz']['rho'])]),
                               advanced=False)
        cds = lft.cds
        _, controls = lft.draw(cds)
        cds.selected.indices = [0]
        self.click(controls.children[-1])
        assert_refused(cds, controls.elements[0], 'porosity')

        # The name after the substitution is taken
        lft = LithoFluidsTable(LithoFluids([LithoFluid(default='brine_sst'), LithoFluid(name='BRINE_SST_HC')]),
                               advanced=False)
        cds = lft.cds
        _, controls = lft.draw(cds)
        cds.selected.indices = [0]
        self.click(controls.children[-1])
        assert_refused(cds, controls.elements[0], 'already')

        # A quasi 2D litho fluid
        lft = LithoFluidsTable(LithoFluids([LithoFluid(name='Quasi 2D', vp=lambda _i: Q_(3000. + _i, 'm/s'))]),
                               advanced=False)
        cds = lft.cds
        _, controls = lft.draw(cds)
        cds.selected.indices = [0]
        self.click(controls.children[-1])
        assert_refused(cds, controls.elements[0], 'quasi 2D')

    def test_renamed_litho_fluid_in_model_table(self):
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable
        from blixt_geo_py.core.models import Layer, Model, ModelTable
        sand, shale = LithoFluid(default='brine_sst'), LithoFluid(default='shale')
        lft = LithoFluidsTable(LithoFluids([sand, shale]), advanced=False)
        lf_cds = lft.cds
        _, controls = lft.draw(lf_cds)
        model = Model(depth_to_top=Q_(1000., 'm'), layers=[Layer(name='L1', litho_fluid=shale),
                                                           Layer(name='L2', litho_fluid=sand),
                                                           Layer(name='L3', litho_fluid=shale)])
        model_table = ModelTable(model)
        mod_cds = model_table.cds
        _, model_controls = model_table.draw(mod_cds, lf_cds)
        self.assertEqual(['shale', 'brine_sst', 'shale'], mod_cds.data['litho_fluid'])

        # The fluid substitution adds a new litho fluid, so the layers keep the one they have
        lf_cds.selected.indices = [0]
        self.click(controls.children[-1])
        self.click(self.apply_button(controls.elements[0]))
        self.assertEqual(['brine_sst', 'shale', 'brine_sst_hc'], lf_cds.data['name'])
        self.assertEqual(['shale', 'brine_sst', 'shale'], mod_cds.data['litho_fluid'])

        # The model keeps all its layers and their values
        update = [_b for _b in model_controls.children if _b.label == 'Update'][0]
        self.click(update)
        self.assertEqual(3, len(model_table.model.layers))
        self.assertEqual('brine_sst', model_table.model.layers[1].litho_fluid.name)
        self.assertAlmostEqual(lf_cds.data['vp'][0], model_table.model.layers[1].litho_fluid.vp.magnitude)

        # A layer can use the new litho fluid
        new_model_data = dict(mod_cds.data)
        new_model_data['litho_fluid'] = ['shale', 'brine_sst_hc', 'shale']
        mod_cds.data = new_model_data
        self.click(update)
        self.assertEqual('brine_sst_hc', model_table.model.layers[1].litho_fluid.name)
        self.assertAlmostEqual(lf_cds.data['vp'][2], model_table.model.layers[1].litho_fluid.vp.magnitude)

        # Renamed by the user, in the table
        new_data = dict(lf_cds.data)
        new_data['name'] = ['brine_sst', 'Draupne', 'brine_sst_hc']
        lf_cds.data = new_data
        self.assertEqual(['Draupne', 'brine_sst_hc', 'Draupne'], mod_cds.data['litho_fluid'])

        # A deleted row is not a new name
        lf_cds.selected.indices = [0]
        delete = [_b for _b in controls.children if _b.label == 'Delete selected rows'][0]
        self.click(delete)
        self.assertEqual(['Draupne', 'brine_sst_hc', 'Draupne'], mod_cds.data['litho_fluid'])

    def test_table(self, unit_test=True):
        from bokeh.io import output_file
        from bokeh.plotting import show, row, column
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable
        output_file(os.path.join(project_dir, 'blixt_geo_py\\results_table\\plot.html'))

        lfs = LithoFluids(litho_fluids=[LithoFluid(default='shale'), LithoFluid(default='brine_sst')])
        lfs.__add__(LithoFluid(name='Test_None', vp=None))
        lfs.__add__(LithoFluid(name='Test_Pint', vp=Q_(3., 'km/s')))

        lft = LithoFluidsTable(lfs, advanced=False)

        cds = lft.cds
        lf_table, lf_controls = lft.draw(cds)
        self.assertTrue(True)
        if unit_test:
            show(column(
                lf_table,
                lf_controls
            ))
            return None
        else:
            return lf_table, lf_controls

    def test_quasi_2D_table(self, unit_test=True):
        from bokeh.io import output_file
        from bokeh.plotting import show, row, column
        from blixt_geo_py.core.core import LithoFluid, LithoFluids, LithoFluidsTable
        output_file(os.path.join(project_dir, 'blixt_geo_py\\results_table\\plot.html'))

        def vp(_i):
            return Q_(3000. +  5. * _i, 'm/s')
        lf1 = LithoFluid(name='Quasi 2D', vp=vp)
        lfs = LithoFluids(litho_fluids=[LithoFluid(default='shale'), lf1, LithoFluid(default='brine_sst')])
        lft = LithoFluidsTable(lfs)

        cds = lft.cds
        lf_table, lf_controls = lft.draw(cds)
        self.assertTrue(True)
        if unit_test:
            show(column(
                lf_table,
                lf_controls
            ))
            return None
        else:
            return lf_table, lf_controls
