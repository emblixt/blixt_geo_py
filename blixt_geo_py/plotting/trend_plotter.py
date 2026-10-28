"""
Plots a single parameter (e.g. Vp) from multiple wells, from specific intervals (or whole well) using cut offs or not
and calculates the trend vs.TVD for that parameter
"""
import logging
import os.path
import unittest

import numpy as np
from bokeh.models import PanTool, BoxZoomTool, WheelZoomTool, ResetTool, SaveTool, CrosshairTool, HoverTool, TextInput
from bokeh.models import (Slider, ColorPicker, Range1d, LinearAxis, LogAxis, Span, Legend, ColumnDataSource, Text,
                          CustomJS, CustomJSTransform, LinearColorMapper, CheckboxEditor, Select)
from bokeh.plotting import column, row
from bokeh.plotting import figure, show


from blixt_geo_py.core.core import Intervals
from blixt_geo_py.core.core import Cutoffs
from blixt_geo_py.plotting.cross_plotter import CrossPlotter

logger = logging.getLogger(__name__)


class TrendPlotter(CrossPlotter):
    """
    Class for handling the (depth) trend plots

    Intended use
    > data_sources = ...  # See cross_plotter.py DataSource for explanation
    > working_intervals = ...
    > cutoffs = ...
    > dt_plot = DepthTrendPlotter(data_sources, working_intervals, cutoffs)
    >
    """
    def __init__(self,
                 data_sources: dict,
                 x: str,
                 y: str | None = None,
                 working_intervals: Intervals | None = None,
                 cutoffs: Cutoffs | None = None,
                 width: int | None = None,
                 height: int | None = None,
                 tools: list | None = None,
                 project_table: str | None = None):
        """
        Plots the data in data_sources in a x vs. y cross plot, where x is the independent variable
        (typically TVD) and y is the dependent variable (e.g. Vp), and it tries to find the function
        f(x) that best matches y(x)

        :param data_sources:
            dict of DataSource objects
            e.g.
                {w.name: w.data_source() for w in project.wells}
            where project is a Project object from project.py

        :param x:
            str
            Name of the independent variable (e.g. 'tvd')
        :param y:
            str
            Name of the dependent variable (e.g. 'vp_oil')

        :param working_intervals:
        :param cutoffs:
        :param width:
        :param height:
        :param tools:
        :param project_table:
            str
            Full path name of excel (typically the project table excel file) to where we can
            write the results
        """
        if width is None:
            width = 900
        self.project_table = project_table

        super().__init__(data_sources, x, y, working_intervals, cutoffs, width, height, tools)

    def calc_trend(self,
                   x_param: str,
                   y_param: str,
                   cds: ColumnDataSource,
                   verbose: bool = False):
        """
        :param x_param:
            str
            Name of the x parameter (independent variable)
        :param y_param:
            str
            Name of the y parameter (dependent variable)
        :param cds:
        :param p:
            bokeh.plotting figure
        :param verbose:
        :return:
        """
        from blixt_geo_py.misc.curve_fitting import (linear_function,
                                                    calculate_depth_trend)
        target_function = linear_function

        result = calculate_depth_trend(
            cds.data[y_param],
            cds.data[x_param],
            target_function,
            [1., 1.],
            mask = cds.data['mask'],
            verbose=verbose,
            xlabel=y_param,
            ylabel=x_param
        )
        # Create a line_cds of the fitted trend curve
        m_m = self.min_and_max()
        x = np.linspace(m_m[self.x][0], m_m[self.x][1], 100)
        _dict = dict(x = np.linspace(m_m[self.x][0], m_m[self.x][1], 100),
                     y = target_function(x, *result[0].x), # Index zero, 0, because we only calculate one trend, discrete_intervals = False
                     label=['{} trend in {}, {}'.format(
                         y_param,
                         ', '.join(self.active_intervals),
                         ', '.join(self.active_cutoffs))]*100
                     )

        return ColumnDataSource(_dict), result[0]

    def plot_trend(self,
                   p: figure,
                   line_cds: ColumnDataSource):
        """
        Draws the line given by the line_cds (keys x and y) in the figur p
        
        :param p: 
        :param line_cds:
        :param line_renderer
        :return: 
        """
        # Clear previous line
        p.renderers = [r for r in p.renderers if r.glyph.__class__.__name__ != 'Line']

        line_renderer = p.line(
            x='x',
            y='y',
            legend_label=line_cds.data['label'][0],
            line_width=2,
            source=line_cds
        )

        # Clear the legend from the previous legend
        p.legend.items = [item for item in p.legend.items if line_renderer in item.renderers]

    def draw(self, cds: ColumnDataSource, set_all_intervals_active: bool = False, verbose: bool = False):
        from bokeh.models import Button, Tooltip
        calc_trend_tooltip = Tooltip(content='Calculate trend for shown data', position='right')
        calc_save_tooltip = Tooltip(content=
                                    'Calculate trends for all common y variables, and saves the result',
                                    position='right')
        # Tooltips on Button doesn't work, try this CustomJS solution instead:
        #  # Use CustomJS to add a tooltip via JavaScript
        #  tooltip_js = CustomJS(args=dict(btn=button), code="""
        #      btn.el.title = "This is a tooltip added via CustomJS";
        #  """)

        #  # Trigger the JS when the document is ready
        #  button.js_on_event('document_ready', tooltip_js)

        if verbose:
            cds.js_on_change('patching', CustomJS(
                args=dict(source=cds),
                code="""
                console.log('Patching event detected in TrendPlotter');
                """
            ))

            cds.js_on_change('data', CustomJS(
                args=dict(source=cds),
                code="""
                console.log('Data event detected in TrendPlotter');
                """
            ))

        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = super().draw(cds)
        x_menu.disabled = True

        def calc_trend_func():
            line_cds, res = self.calc_trend(x_menu.value, y_menu.value, cds, verbose=verbose)
            self.plot_trend(xplot, line_cds)

        calc_trend = Button(label='Calculate trend', button_type='success')
        calc_trend.on_click(calc_trend_func)

        def calc_save_func():
            from blixt_geo_py.misc.io import write_regression
            for y_param in y_menu.options:
                if y_param in ['md', 'tvd', 'twt']:  # don't calculate trends for these
                    continue
                line_cds, res = self.calc_trend(x_menu.value, y_param, cds, verbose=verbose)
                print(y_param, res['success'], res['x'])
                if res['success'] and self.project_table is not None:
                    print('Trying to save results')
                    write_regression(self.project_table,
                                     res['x'],
                                     y_param,
                                     ', '.join(list(self._data_sources.keys())),
                                     ', '.join(self.active_intervals),
                                     'Linear',
                                     note=line_cds.data['label'][0])

        calc_all_and_save = Button(label='Calculate trends and save',
                                   button_type='success')
        calc_all_and_save.on_click(calc_save_func)

        return (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask,
                ct_guis,
                wis_guis,
                calc_trend, calc_all_and_save)

class TestCases(unittest.TestCase):

    def test_data_cds(self):
        from blixt_geo_py.unit_tests.test_cross_plotter import make_data_sources

        ds1, ds2, wis, coffs = make_data_sources()

        tp = TrendPlotter({str(_s.name):_s for _s in [ds1, ds2]},
                          x='md',
                          y='var_two',
                          cutoffs=coffs,
                          working_intervals=wis,
                          project_table="C:\\Users\\emb\\Downloads\\Book.xlsx")

        d_cds = tp.cds

        return tp.draw(d_cds)

    def test_calc_trend(self):
        import matplotlib.pyplot as plt
        from blixt_geo_py.unit_tests.test_cross_plotter import make_data_sources

        ds1, ds2, wis, coffs = make_data_sources()

        tp = TrendPlotter({str(_s.name):_s for _s in [ds1, ds2]},
                          x='md',
                          y='var_two',
                          cutoffs=coffs,
                          working_intervals=wis)
        cds = tp.cds
        tp.calc_trend(cds, verbose=True)

        plt.show()
