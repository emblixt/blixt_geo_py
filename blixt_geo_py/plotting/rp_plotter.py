"""
Plots log data from multiple wells, from specific intervals (or whole well) using cut offs or not
using standard modulus or other parameters used in rock physics (e.g. bulk & shear modulus, poisson ratio, vp/vs ratio
"""
import logging
import os.path
from typing import Callable

import numpy as np
import pint
from bokeh.io import output_file
from bokeh.models import PanTool, BoxZoomTool, WheelZoomTool, ResetTool, SaveTool, CrosshairTool, HoverTool, TextInput
from bokeh.models import (Slider, ColorPicker, Range1d, LinearAxis, LogAxis, Span, Legend, ColumnDataSource, Text,
                          CustomJS, CustomJSTransform, LinearColorMapper, CheckboxEditor, Select)
from bokeh.plotting import column, row
from bokeh.plotting import figure

project_dir = str(os.path.dirname(__file__).replace('blixt_geo_py\\blixt_geo_py\\plotting', ''))

from blixt_geo_py.rp.rp_wrapper import data_source_moduli
from blixt_geo_py.core.core import Intervals
from blixt_geo_py.core.core import Cutoffs
from blixt_geo_py.plotting.cross_plotter import CrossPlotter

output_file(os.path.join(project_dir, 'blixt_geo_py\\results_folder\\plot.html'))
logger = logging.getLogger(__name__)


class RockPhysicsPlotter(CrossPlotter):
    """
    Class for handling the rock physics plot

    Intended use
    > data_sources = ...  # See cross_plotter.py DataSource for explanation
    > working_intervals = ...
    > cutoffs = ...
    > rp_plot = RockPhysicsPlotter(data_sources, working_intervals, cutoffs)
    >

    NOTE the data_sources must have
    """
    def __init__(self,
                 wells: list,
                 log_tables: list,
                 working_intervals: Intervals | None = None,
                 cutoffs: Cutoffs | None = None,
                 width: int | None = None,
                 height: int | None = None,
                 tools: list | None = None
                 ):
        """
        Plots the data in data_sources in a x vs. y cross plot,

        :param wells:
            list
            List of Well objects
        :param log_tables:
            list
            List of LogTable objects:
                LogTable(
                    name='so08',
                    log_table={'P velocity': 'vp_so08', 'S velocity': 'vs_so08', 'Density': 'rho_so08',
                               'Porosity': 'phie', 'Volume': 'vcl'}
                )
            Each LogTable must include P velocity, S velocity and Density, and these should point to the well
            logs inside the well that will be used to calculate the Rock Physics parameters (moduli).
            But the LogTable can also include other logs (e.g. Porosity and Volume shale) that are useful for
            display, in particular for CutoffRules.

        :param working_intervals:
        :param cutoffs:
        :param width:
        :param height:
        :param tools:
        """

        if width is None:
            width = 900

        # Calculate the elastic moduli for the well(s) for the different LogTables
        elastic_mod_sources = {}
        for _well in wells:
            for _log_table in log_tables:
                wds = _well.data_source(log_table=_log_table, verbose=False)
                data_source_moduli(wds, _log_table, verbose=False)
                elastic_mod_sources[wds.name] = wds

        self._rpt_table = None

        super().__init__(elastic_mod_sources, working_intervals=working_intervals, cutoffs=cutoffs, width=width,
                         height=height, tools=tools)

    def rpt_table(self,
                  rpt_variable: pint.Quantity | None = None,
                  rpt_constants: pint.Quantity | None = None,
                  rpt_function: Callable | None = None,
                  rpt_annotations: list | None = None,
                  ):
        """
        Creates the RPT table and sets up the initial RPT data

        :param rpt_variable:
            Pint Quantity with an np.array of length N
            values used to draw the rock physics template, preferably less than about 10 items long for creating
            nice plots
        :param rpt_constants:
            Pint Quantity with a list
            list of length M of constants (pint quantities) used to parametrize the rpt function
        :param rpt_function:
            function
            Rock physics template function of rpt_variable
            Should take a second argument which is used to parameterize the function
            e.g.
            def rpt(rpt_variable, rpt_constants, **rpt_keywords):
                return c*t + rpt_keywords.pop('zero_crossing', 0)
        :param rpt_annotations:
            list of same length as rpt_constants
            Used to annotate the rock physics template

        :return:
        """
        from blixt_geo_py.rp.rp_wrapper import return_rpt_keywords, rpt_wrapper, rpt_to_moduli, RptVariableTable

        if (rpt_variable is None) or (rpt_constants is None) or (rpt_function is None) or (rpt_annotations is None):
            return None, None, None, None, None, None, None

        self._rpt_table = RptVariableTable()
        table_cds = self._rpt_table.cds

        _vp, _vs, _rho = rpt_wrapper(rpt_variable, rpt_function, rpt_constants, return_rpt_keywords())
        _dict = rpt_to_moduli(_vp, _vs, _rho, rpt_annotations)
        rpt_lines_cds = ColumnDataSource(_dict)

        rpt_dt, add_row, var_select, delete_row, update_table, rpt_lines_cds = self._rpt_table.draw(
            table_cds,
            rpt_lines_cds,
            t=rpt_variable,
            rpt=rpt_function,
            constants=rpt_constants,
            rpt_annotations=rpt_annotations)

        return table_cds, rpt_lines_cds, rpt_dt, add_row, var_select, delete_row, update_table

    def draw(self,
             cds: ColumnDataSource,
             rpt_variable: pint.Quantity | None = None,
             rpt_constants: pint.Quantity | None = None,
             rpt_function: Callable | None = None,
             rpt_annotations: list | None = None,
             set_all_intervals_active: bool = False,
             verbose: bool = False):
        """
        Draws the cross plot and more

        :param rpt_variable:
            Pint Quantity with an np.array of length N
            values used to draw the rock physics template, preferably less than about 10 items long for creating
            nice plots
        :param rpt_constants:
            Pint Quantity with a list
            list of length M of constants (pint quantities) used to parametrize the rpt function
        :param rpt_function:
            function
            Rock physics template function of rpt_variable
            Should take a second argument which is used to parameterize the function
            e.g.
            def rpt(rpt_variable, rpt_constants, **rpt_keywords):
                return c*t + rpt_keywords.pop('zero_crossing', 0)
        :param rpt_annotations:
            list of same length as rpt_constants
            Used to annotate the rock physics template

        :return:
        """
        from bokeh.models import Button, Tooltip

        if verbose:
            cds.js_on_change('patching', CustomJS(
                args=dict(source=cds),
                code="""
                console.log('Patching event detected in RockPhysicsPlotter');
                """
            ))

            cds.js_on_change('data', CustomJS(
                args=dict(source=cds),
                code="""
                console.log('Data event detected in RockPhysicsPlotter');
                """
            ))

        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = super().draw(cds)
        style_table = self.add_data_source_style(cds)

        table_cds, rpt_lines_cds, rpt_dt, add_row, var_select, delete_row, update_table = self.rpt_table(
            rpt_variable=rpt_variable,
            rpt_constants=rpt_constants,
            rpt_function=rpt_function,
            rpt_annotations=rpt_annotations
        )

        # When there is no RPT table or plot, return results now, with rpt related results set to None
        if table_cds is None:
            return (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask,
                    ct_guis,
                    wis_guis,
                    style_table,
                    rpt_dt, add_row, var_select, delete_row, update_table)

        # We begin with the initial setup
        new_data = dict(rpt_lines_cds.data)
        if x_menu.value in list(new_data.keys()):
            new_data['xs'] = new_data[x_menu.value]
        else:
            new_data['xs'] = new_data['ai']  # Default back to plot AI, the axes will be mixed up though
        if y_menu.value in list(new_data.keys()):
            new_data['ys'] = new_data[y_menu.value]
        else:
            new_data['ys'] = new_data['ai']  # Default back to plot AI, the axes will be mixed up though
        rpt_lines_cds.data = new_data

        # The rpt_lines_cds needs to be updated when x_menu or y_menu is updated similar to how the crossplot
        # cds is updated
        _args_dict = dict(x_drop=x_menu, y_drop=y_menu, x_y_source=rpt_lines_cds)
        _code = """
            const x_param = x_drop.value;
            const y_param = y_drop.value;
            var new_data = x_y_source.data;
            
            // REPLACE DATA
            new_data['xs'] = x_y_source.data[x_param];
            new_data['ys'] = x_y_source.data[y_param];
            console.log('dropdown: ' + cb_obj.value, x_param);
            x_y_source.data = new_data;
            x_y_source.change.emit();
        """
        x_menu.js_on_change(
            'value',
            CustomJS(
                args=_args_dict,
                code=_code)
        )
        y_menu.js_on_change(
            'value',
            CustomJS(
                args=_args_dict,
                code=_code)
        )

        xplot.multi_line(xs='xs', ys='ys', line_color='colors', line_width=3, legend_field='labels',
                         source=rpt_lines_cds)

        return (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask,
                ct_guis,
                wis_guis,
                style_table,
                rpt_dt, add_row, var_select, delete_row, update_table)
