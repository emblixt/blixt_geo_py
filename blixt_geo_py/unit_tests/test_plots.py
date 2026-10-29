import os
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
from blixt_geo_py.unit_tests.plot_settings import show_or_close

import blixt_geo_py.io.io as uio
import matplotlib.pyplot as plt
from blixt_geo_py.plotting.helpers import header_plot, axis_plot
from blixt_geo_py.plotting.log_plotter import LogPlotter
from blixt_geo_py.plotting.plot_logs import plot_logs

from blixt_geo_py import Q_
from blixt_geo_py.core.core import Interval, Intervals, LogTable, StratUnit
from blixt_geo_py.core.project import Project
from blixt_geo_py.core.well import Well


class PlotTestCase(unittest.TestCase):
    # Logs to read from Well D, as log type: log name. read_las() does not support several logs per log type
    log_table = LogTable({
        'Sonic': 'ac',
        'Shear sonic': 'acs',
        'Caliper': 'cali',
        'Density': 'den',
        'Gamma ray': 'gr',
        'Resistivity': 'rdep',
        'Neutron density': 'neu'})

    # Working intervals, as top and base in meters MD
    working_intervals = {
        'SAND C': [1585.0, 1826.0],
        'SHALE C': [1585.0, 1826.0],
        'SAND D': [1826.0, 1878.0],
        'SAND E': [1878.0, 1984.0],
        'SAND F': [1984.0, 2158.0],
        'SHALE G': [2158.0, 2211.0],
        'SAND H': [2211.0, 2365.0]
    }

    @classmethod
    def setUpClass(cls):
        cls.wp = Project(name='MyProject')
        cls.w = Well()
        cls.w.read_las(os.path.join(cls.wp.working_dir, 'test_data', 'Well D.las'), log_table=cls.log_table)
        # The md log is used as the depth axis
        cls.w.create_md_log()
        cls.wis = Intervals(intervals=[
            Interval(cls.w.name, Q_(top, 'm'), Q_(base, 'm'), StratUnit(wi_name, 1))
            for wi_name, (top, base) in cls.working_intervals.items()])

    def test_axis_header(self):
        templ = uio.project_templates(PlotTestCase.wp.project_table)
        fig, ax = plt.subplots()
        log_types = ['P velocity', 'Density', 'Caliper', 'Resistivity']
        limits = [[templ[x]['min'], templ[x]['max']] for x in log_types]
        legends = ['test [{}]'.format(templ[x]['unit']) for x in log_types]
        styles = [{'lw': templ[x]['line width'],
                   'color': templ[x]['line color'],
                   'ls': templ[x]['line style']} for x in log_types]
        header_plot(ax, limits, legends, styles)
        show_or_close()
        with self.subTest():
            self.assertTrue(True)

    def test_axis_plot(self):
        templ = uio.project_templates(PlotTestCase.wp.project_table)
        fig = plt.figure()
        ax = fig.add_subplot(2, 2, 1)
        log_types = ['Gamma ray', 'Caliper']
        limits = [[templ[x]['min'], templ[x]['max']] for x in log_types]
        # Harmonize the logs, so that the data and the depth have the same length
        data = PlotTestCase.w.dict()
        values = [data[PlotTestCase.w.get_logs_of_type(x)[0].name].magnitude for x in log_types]
        y = data['md'].to('m').magnitude
        styles = [{'lw': templ[x]['line width'],
                   'color': templ[x]['line color'],
                   'ls': templ[x]['line style']} for x in log_types]
        axis_plot(ax, y, values, limits, styles, nxt=2)

        show_or_close()

    def test_plot_logs(self):
        # One column of log names for each column in the plot
        plotter = plot_logs(PlotTestCase.w, [['ac', 'acs'], ['den', 'neu'], ['rdep']],
                            PlotTestCase.wis, ['SAND E'], buffer=50.)
        with self.subTest():
            self.assertIsInstance(plotter, LogPlotter)
            self.assertEqual(3, len(plotter.columns))
