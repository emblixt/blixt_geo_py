import os
import tempfile
import unittest

from openpyxl import load_workbook

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\unit_tests', ''))

import blixt_geo_py.io.io as uio
from blixt_geo_py.core.core import AttributeDict, Header, LogTable
from blixt_geo_py.core.well import Well
from blixt_geo_py.io.io import read_las_file
from blixt_geo_py.core.log_curve import read_las as read_log_curves


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


def read_las(lfile, rename_logs=None):
    well_dict, data = read_las_file(lfile, rename_logs=rename_logs)
    null_value = well_dict['well_info']['null']['value']
    return null_value, list(data.keys()), well_dict, data


class LasTestCase(unittest.TestCase):

    def test_read_las(self):
        for _las_file in las_files:
            null_value, gen_keys, well_dict, data = read_las(_las_file)
            with self.subTest(os.path.basename(_las_file)):
                # every curve in the header has data, of the same length as all the other curves
                self.assertEqual(gen_keys, list(well_dict['curve'].keys()))
                self.assertEqual(1, len({len(_d) for _d in data.values()}))

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
        null_value, gen_keys, well_dict, all_data = read_las(las_file)
        var_name = gen_keys[1]
        data = np.array(all_data[var_name])
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
        """
        Header values are cleaned: well names harmonized, empty values are None, a unit given after the value
        is moved to the unit, and text after a ':' in the value is kept
        """
        _las_file = os.path.join(test_data_dir, 'WrongWellInfo.las')
        null_value, gen_keys, well_dict, data = read_las(_las_file)
        well_info = well_dict['well_info']
        self.assertEqual('6507_5_8', well_info['well']['value'])
        self.assertEqual(-999., null_value)
        self.assertIsNone(well_info['loc']['value'])
        self.assertEqual((30., 'm'), (well_info['apdat']['value'], well_info['apdat']['unit']))
        self.assertEqual((100., 'FT'), (well_info['kb']['value'], well_info['kb']['unit']))
        self.assertEqual('Original database: PL1057_1069', well_info['com1']['value'])

    def test_duplicate_well_name(self):
        """ Well F.las has two WELL lines. The first is used """
        null_value, gen_keys, well_dict, data = read_las(os.path.join(test_data_dir, 'Well F.las'))
        self.assertEqual('WELL_F', well_dict['well_info']['well']['value'])

    def test_rename_to_existing_name(self):
        """
        L-30.las contains both DEPTH and DEPT. When both are renamed to 'depth', only the first is kept,
        and its data is not mixed with the data of the second
        """
        _las_file = os.path.join(test_data_dir, 'L-30.las')
        null_value, gen_keys, well_dict, data = read_las(_las_file, rename_logs={'depth': ['DEPTH', 'DEPT']})
        self.assertEqual(1, gen_keys.count('depth'))
        self.assertNotIn('dept', gen_keys)
        self.assertEqual(len(data['cald']), len(data['depth']))
        log_curves, _ = read_log_curves(_las_file, rename_logs={'depth': ['DEPTH', 'DEPT']})
        self.assertEqual(len(data['cald']), len(log_curves['cald'].depth))

    def test_two_depth_curves(self):
        """
        WellWithTwoDeptCurves.las contains the DEPTH curve twice, in column 1 and 4.
        Only the first DEPTH is kept, with a warning, and the curves after the second DEPTH are not shifted
        """
        _las_file = os.path.join(test_data_dir, 'WellWithTwoDeptCurves.las')
        w = Well()
        with self.assertLogs('blixt_geo_py.io.io', level='WARNING') as logs:
            w.read_las(_las_file)
        self.assertTrue(any('DEPTH occurs more than once' in _msg for _msg in logs.output))

        self.assertEqual(['depth', 'phie', 'rho_dry', 'rho_sg08', 'rho_so08', 'sw', 'vp_dry', 'vp_sg08', 'vp_so08',
                          'vs_dry', 'vs_sg08', 'vs_so08', 'vsh'], sorted(w.get_log_names))
        logs = {_log.name: _log for _log in w.logs}
        for _name, _log in logs.items():
            with self.subTest(_name):
                self.assertEqual(100, len(_log.values))
                self.assertEqual(100, len(_log.depth))
        depth = logs['vp_so08'].depth.values
        self.assertAlmostEqual(2200., depth[0])
        self.assertAlmostEqual(2215.0876, depth[-1])
        np.testing.assert_allclose(logs['depth'].values, depth)
        # Values in the columns after the second DEPTH
        self.assertAlmostEqual(3631.9007, logs['vp_so08'].values[0])
        self.assertAlmostEqual(4013.0207, logs['vp_so08'].values[-3])
        self.assertAlmostEqual(2387.5609, logs['vs_dry'].values[-3])
        self.assertAlmostEqual(0.2, logs['sw'].values[-1])

    def test_las_3(self):
        """ LAS 3.0 files are read too """
        null_value, gen_keys, well_dict, data = read_las(os.path.join(test_data_dir, 'Well E_CPI.las'))
        self.assertEqual(['depth', 'phie', 'phit', 'sw', 'vsh'], gen_keys)
        self.assertEqual('WELL_E', well_dict['well_info']['well']['value'])

    def test_quoted_names(self):
        """
        Quoted names containing spaces are read correctly, both in the header and in the data section.
        Curves with text data are skipped
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            _las_file = os.path.join(tmp_dir, 'quoted.las')
            with open(_las_file, 'w') as f:
                f.write('~V\nVERS. 2.0 :\nWRAP. NO :\n~W\nNULL. -999.25 :\nWELL. "35/4-3 A" : WELL\n'
                        '~C\nDEPT.M :\nZONE. : zone\nGR.GAPI :\n~A\n1 "Upper Zone" 50\n2 "Lower Zone" -999.25\n')
            null_value, gen_keys, well_dict, data = read_las(_las_file)
        self.assertEqual('35_4_3A', well_dict['well_info']['well']['value'])
        self.assertEqual(['dept', 'gr'], gen_keys)
        self.assertEqual(50., data['gr'][0])
        self.assertTrue(np.isnan(data['gr'][1]))

    def test_no_depth(self):
        """ A las file without a depth curve gives no logs, and no error """
        with tempfile.TemporaryDirectory() as tmp_dir:
            _las_file = os.path.join(tmp_dir, 'no_depth.las')
            with open(_las_file, 'w') as f:
                f.write('~V\nVERS. 2.0 :\nWRAP. NO :\n~W\nNULL. -999.25 :\nWELL. W-1 : WELL\n'
                        '~C\nTIME.S :\nGR.GAPI :\n~A\n1 50\n2 -999.25\n')
            log_curves, well_dict = read_log_curves(_las_file)
            w = Well()
            w.read_las(_las_file)
        self.assertEqual({}, log_curves)
        self.assertEqual('W_1', well_dict['well_info']['well']['value'])
        self.assertIsNone(w.logs)


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

class SumsAndAveragesTestCase(unittest.TestCase):
    def test_null_value(self):
        """
        NaN is written as the null value -999.25, which must be read back as NaN and not as e.g. a velocity
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            file_name = os.path.join(tmp_dir, 'SumsAndAverages.xlsx')
            uio.write_sums_and_averages(file_name, ['With data', 'WELL_A', 'MD', -999.25, -999.25, -999.25,
                                                    3000., 1500., 2.3])
            uio.write_sums_and_averages(file_name, ['No data', 'WELL_B', 'MD', -999.25, -999.25, -999.25,
                                                    np.nan, np.nan, np.nan])

            wb = load_workbook(file_name)
            rows = list(wb.active.iter_rows(values_only=True))
            wb.close()
            data = uio.read_sums_and_averages(file_name)

        written = dict(zip(rows[20], rows[22]))
        self.assertEqual(-999.25, written['VpMean'])
        self.assertEqual('WELL_B', data['No data']['Well'])
        self.assertEqual(3000., data['With data']['VpMean'])
        self.assertEqual(2.3, data['With data']['RhoMean'])
        for _name in ['VpMean', 'VsMean', 'RhoMean']:
            self.assertTrue(np.isnan(data['No data'][_name]), _name)
        self.assertTrue(np.isnan(data['With data']['TopDepth']))


class PetrelPointsTestCase(unittest.TestCase):
    def test_read_points(self):
        f = os.path.join(test_data_dir, 'PetrelPointsWAttributes.ascii')
        result = uio.read_petrel_points(f)
        print(result)
