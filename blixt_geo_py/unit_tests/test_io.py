import os
import unittest

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))

import blixt_geo_py.io.io as uio
from blixt_geo_py.core.core import AttributeDict, Header, LogTable
from blixt_geo_py.core.well import Well
from blixt_geo_py.io.io import well_reader


import numpy as np

test_data_dir = os.path.join(project_dir, 'blixt_geo_py\\test_data')
las_file = os.path.join(test_data_dir, 'Well A.las')
las_files = [os.path.join(test_data_dir, _las) for _las in ['Well A.las',
                                                             'Well A more data.las',
                                                             'Well B.las',
                                                             'Well C.las',
                                                             'Well D.LAS',
                                                             'Well E_CPI.las',
                                                             'Well E_CPI test copy.las',
                                                             'Well F.las',
                                                             'L-30.las',
                                                             'WrongWellInfo.las']]


def read_las(lfile):
    with open(lfile, 'r') as f:
        lines = f.readlines()
    null_value, gen_keys, well_dict = well_reader(lines)
    return null_value, gen_keys, well_dict


class LasTestCase(unittest.TestCase):

    def test_read_las(self):
        for _las_file in las_files:
            null_value, gen_keys, well_dict = read_las(_las_file)
            with self.subTest():
                print('\n', os.path.basename(_las_file))
                print(gen_keys)
                print(list(well_dict['well_info'].keys()))
                print(len(gen_keys), len(list(well_dict['data'].keys())))
                self.assertEqual(len(gen_keys), len(list(well_dict['data'].keys())))

    def test_header_types(self):
        """
        The well header, and the header of each log, is a Header. The sections of the las file that read_las() stores
        in the well header, e.g. well_info, are AttributeDicts, so their items can also be accessed as attributes
        :return:
        """
        w = Well()
        w.read_las(las_file, log_table=LogTable({'Porosity': 'phie'}))
        with self.subTest('well header'):
            self.assertIsInstance(w.header, Header)
        with self.subTest('log headers'):
            for _log in w.logs:
                self.assertIsInstance(_log.header, Header, _log.name)
        with self.subTest('las sections'):
            # The 'other' section is free text, and is stored as a string
            for key in ['well_info', 'version', 'parameter', 'curve']:
                self.assertIsInstance(w.header[key], AttributeDict, key)
        with self.subTest('attribute access'):
            self.assertEqual(w.header['well_info']['well']['value'], w.header.well_info.well.value)

    def test_read_las_multi_log_table(self):
        """
        read_las() reads all the logs in a LogTable that mixes single log names and lists of log names
        """
        w = Well()
        w.read_las(os.path.join(test_data_dir, 'Well D.las'),
                   log_table=LogTable({'Density': 'den', 'Resistivity': ['rdep', 'rmed', 'rsha']}))
        self.assertEqual(['den', 'rdep', 'rmed', 'rsha'], sorted(w.get_log_names))
        self.assertEqual(['rdep', 'rmed', 'rsha'], sorted(_l.name for _l in w.get_logs_of_type('Resistivity')))

    def test_null_value(self):
        """
        When reading in a las file, any 'null values' should be replaced with np.nan
        :return:
        """
        null_value, gen_keys, well_dict = read_las(las_file)
        var_name = gen_keys[1]
        data = np.array(well_dict['data'][var_name])
        # data should not contain explicit 'null_value's, so below null_data should have length zero
        null_data = data[data == float(null_value)]
        with self.subTest():
            print(var_name, null_value, len(null_data))
            self.assertEqual(0, len(null_data))
        with self.subTest():
            # these test data should contain NaN's, so t below should contain some True elements
            t = np.isnan(data)
            print('Data contains NaN:', any(t))
            self.assertTrue(any(t))

    def test_well_info(self):
        _las_file = os.path.join(test_data_dir, 'WrongWellInfo.las')
        null_value, gen_keys, well_dict = read_las(_las_file)
        for key in list(well_dict['well_info'].keys()):
            print(well_dict['well_info'][key]['value'], type(well_dict['well_info'][key]['value']))


class UtilsTestCase(unittest.TestCase):
    well_table = {'test_data/Well A.las':
                      {'Given well name': 'WELL_A',
                       'logs': {
                           'vp_dry': 'P velocity',
                           'vp_gas': 'P velocity',
                           'vs_dry': 'S velocity',
                           'vs_gas': 'S velocity',
                           'vs_test': 'S velocity',
                           'rho_dry': 'Density',
                           'rho_gas': 'Density',
                           'phie': 'Porosity',
                           'vcl': 'Volume'},
                       'Translate log names': 'Vs_gas->Vs_g, VS_TEST->VS_T, phie->phi',
                       'Note': 'Some notes for well A'},
                  'test_data/Well B.las':
                      {'Given well name': 'WELL_B',
                       'logs': {
                           'vp_dry': 'P velocity',
                           'vp_sg08': 'P velocity',
                           'vs_dry': 'S velocity',
                           'vs_sg08': 'S velocity',
                           'rho_dry': 'Density',
                           'rho_sg08': 'Density',
                           'phie': 'Porosity',
                           'vcl': 'Volume'},
                       'Translate log names': 'vs_sg08->Vs_g, phie->phi',
                       'Note': 'Some notes for well B'}}
    def test_well_table(self):
        wt = UtilsTestCase.well_table
        out = uio.invert_well_table(wt, well_name='WELL_A', rename=True)
        with self.subTest():
            print(out)
            self.assertTrue(True)

class OthersTestCase(unittest.TestCase):
    mask_str = 'VCL>0.8, PHIE>0.1'
    print(uio.interpret_cutoffs_string(mask_str))

class PetrelPointsTestCase(unittest.TestCase):
    def test_read_points(self):
        f = os.path.join(test_data_dir, 'PetrelPointsWAttributes.ascii')
        result = uio.read_petrel_points(f)
        print(result)
