# ----------------------------------------------------------------------------------------------------------
# Filename: cross_plotter.py
#  Purpose: Cross plot data using the bokeh interactive plotting library
#           Similar to crossplot.py, but tried to modernize it
#
# ---------------------------------------------------------------------------------------------------
import logging

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pint
from bokeh.models import PanTool, BoxZoomTool, WheelZoomTool, ResetTool, SaveTool, CrosshairTool, HoverTool, TextInput
from bokeh.models import (Slider, ColorPicker, Range1d, LinearAxis, LogAxis, Span, Legend, ColumnDataSource, Text,
                          CustomJS, CustomJSTransform, LinearColorMapper, CheckboxEditor, Select)
from bokeh.plotting import column, row
from bokeh.plotting import figure, show
# from prompt_toolkit.shortcuts import button_dialog
# from html5lib.constants import mathmlTextIntegrationPointElements
from scipy.stats import wilcoxon

from blixt_geo_py.core.core import Intervals, WorkingIntervalsTable
from blixt_geo_py.core.core import Cutoffs, ClassificationTable, LogTable
from blixt_geo_py.utils.utils import print_info

logger = logging.getLogger(__name__)

default_tools = [
    PanTool(),
    WheelZoomTool(),
    BoxZoomTool(),
    HoverTool(),
    CrosshairTool(),
    ResetTool(),
    SaveTool()
]

cnames = [mcolors.to_hex(tmp['color']) for tmp, j in zip(plt.rcParams['axes.prop_cycle'], range(20))]
markers = ['circle', 'diamond', 'hex', 'inverted_triangle', 'plus', 'square', 'star', 'triangle']


def add_x_y_to_cds(
               cds_dict: dict,
               x: str | None = None,
               y: str | None = None,
               size: float | str | None = None,
               color: str | None = None,
               marker: str | None = None,
               legend_group: str | None = None,
               opacity: float | str | None = None,
               mask: np.ndarray | None = None
               ) -> dict:
    """
    The idea is to let the input decide which variable that should be used on the x-axis, y-axis, size, color,
    marker and legend.
    This function adds the extra keys for 'x', 'y', ... to the original cds dictionary

    E.G.
        if x = 'vp'
        WHEN
        cds_dict = dict(vp=..., vs=..., rho=...)
        THEN
        x_y_cds = dict(vp=..., vs=..., rho=..., x=cds_dict['vp'], y=..., etc...)

    :param cds_dict:
    :param x:
    :param y:
    :param size:
    :param color:
    :param marker:
    :param legend_group:
    :param opacity:
    :param mask:

    :return:
        dict
        transformed_cds
        The dictionary has at least the following keys:
            'x', 'y', 'size', 'color', 'marker' and 'legend_group'
    """
    _vars = list(cds_dict.keys())
    _n = len(cds_dict[_vars[0]])
    _dict = {}

    # for _key in ['x', 'y', 'size', 'color', 'marker', 'legend_group']:
    #     if _key in _vars:
    #         warn_txt = 'The key {} is among the original keys of the input cds and will be overwritten'.format(_key)
    #         print_info(warn_txt, 'warning', logger)


    if x is not None and x in _vars:
        _dict['x'] = cds_dict[x]
    elif x is not None:
        _dict['x'] = x
    else:
        _dict['x'] = cds_dict[_vars[0]]

    if y is not None and y in _vars:
        _dict['y'] = cds_dict[y]
    elif y is not None:
        _dict['y'] = y
    else:
        _dict['y'] = cds_dict[_vars[1]]

    if size is not None and size in _vars:
        _dict['size'] = cds_dict[size]
    elif size is not None:
        _dict['size'] = [size] * _n
    else:
        _dict['size'] = cds_dict['size']

    if color is not None and color in _vars:
        _dict['color'] = cds_dict[color]
    elif color is not None:
        _dict['color'] = [color] * _n
    else:
        _dict['color'] = cds_dict['color']

    if marker is not None and marker in _vars:
        _dict['marker'] = cds_dict[marker]
    elif marker is not None:
        _dict['marker'] = [marker] * _n
    else:
        _dict['marker'] = cds_dict['marker']

    if legend_group is not None and legend_group in _vars:
        _dict['legend_group'] = cds_dict[legend_group]
    elif legend_group is not None:
        _dict['legend_group'] = [legend_group] * _n
    else:
        _dict['legend_group'] = cds_dict['legend_group']

    if opacity is not None and opacity in _vars:
        _dict['opacity'] = cds_dict[opacity]
    elif opacity is not None:
        _dict['opacity'] = [opacity] * _n
    else:
        _dict['opacity'] = cds_dict['opacity']

    if mask is not None:
        _dict['mask'] = mask
    else:
        _dict['mask'] = cds_dict['mask']

    _dict['source_name'] = cds_dict['source_name']

    cds_dict.update(_dict)
    return cds_dict


class DataSource:
    """
    Class containing a dictionary of data, E.G. for one well, which can easily generate a ColumnDataSource
    But can hold some extra attributes and methods that the ColumnDataSource itself cant have
    """
    def __init__(self,
                 name: str | None = None,
                 data: dict | None = None,
                 templates: dict | None = None,
                 mask: np.ndarray | None = None
                 ):
        """
        Container for data related to one well
        :param name:
            str
            Name of data set (e.g. well name)
        :param data:
            dict
            Dictionary of data, with variable names as keys.
            NOTE that we can store the data here as pint Quantities, that is, with units. Very practical!
            Remember that a ColumnDataSource requires that all variable has the same length,
            AND
            ColumnDataSource can not handle pint Quantities as data, which is why we take the magnitude when
            creating the CDS
        :param templates:
            dict
            Dictionary of Template objects for each variable, and preferably also one Template for this
            DataSource itself.
        :param mask:
            np.ndarray of boolean values
            Must have same length as the data (values) in the data dictionary
            True means data is kept
            False means the data is masked out
        """
        self._name = name
        if templates is None:
            templates = {}
        if data is not None:
            for _key in list(data.keys()):
                if _key not in list(templates.keys()):
                    templates[_key] = None
        self._templates = templates
        if 'mask' in list(data.keys()):
            _mask = data['mask']
        elif mask is None:
            _mask = np.array(np.ones(len(data[list(data.keys())[0]])), dtype=bool)
            data['mask'] = _mask
        else:
            _mask = mask
            data['mask'] = _mask
        self.mask = _mask

        self._data = data

    def __len__(self):
        return len(self.data[self.variables[0]])

    def keys(self):
        return self._data.keys()

    @property
    def variables(self):
        return list(self._data.keys())

    @property
    def units(self):
        units = []
        for _key, _value in self._templates.items():
            if _key not in self.variables:
                continue
            # TODO Maybe we should remove '_value is not None', all our data should have units?
            # TODO No, the 'mask' column has no units
            if _value is not None and _value.units is not None:
                units.append(_value.units)
        return units

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, new_name):
        self._name = new_name

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, new_data):
        if not isinstance(new_data, dict):
            raise IOError('Data must be input as a dictionary, not {}'.format(type(new_data)))
        self._data = new_data

    @property
    def templates(self):
        return self._templates

    @templates.setter
    def templates(self, new_templates):
        for _key in list(self.keys()):
            if _key not in list(new_templates.keys()):
                new_templates[_key] = None
        self._templates = new_templates

    @property
    def cds(self) -> ColumnDataSource:
        _data = {}
        # Take only the magnitude if data is provided as pint Quantities
        for _key in list(self.data.keys()):
            if isinstance(self.data[_key], pint.Quantity):
                _data[_key] = self.data[_key].magnitude
            else:
                _data[_key] = self.data[_key]
        return ColumnDataSource(data=_data, name=self.name)

    @cds.setter
    def cds(self, new_cds):
        if isinstance(new_cds, ColumnDataSource):
            self.data = dict(new_cds.data)
        elif isinstance(new_cds, dict):
            self.data = new_cds
        else:
            raise IOError('New cds must be either ColumnDataSource or Dict, not {}'.format(
                type(new_cds)
            ))

    def min_and_max(self):
        return {_key: [np.nanmin(self.data[_key]), np.nanmax(self.data[_key])] for _key in list(self.keys())}

    def calc_mask(self,
                  cutoffs: Cutoffs,
                  logtable: LogTable):
        # TODO
        pass


    # def transform_source_data(self,
    #                      x: None | str = None,
    #                      y: None | str = None,
    #                      size: None | str = None,
    #                      color: None | str = None,
    #                      marker: None | str = None,
    #                      legend_group: None | str = None,
    #                      ) -> dict:
    #     """
    #     The idea is to let the input decide which parameter that should be used on the x-axis, y-axis, size, color,
    #     marker and legend
    #     E.G.
    #         if x = 'vp'
    #         WHEN
    #         self.data = dict(vp=..., vs=..., rho=...)
    #         THEN
    #         transformed_source_data = dict(x=self.data['vp'], y=..., etc...)

    #     :param x:
    #     :param y:
    #     :param size:
    #     :param color:
    #     :param marker:
    #     :param legend_group:

    #     :return:
    #         dict
    #         transformed_source
    #         The dictionary has at least the following keys:
    #             'x', 'y', 'size', 'color', 'marker' and 'legend_group'
    #     """

    #     _n = len(self.data[list(self.keys())[0]])
    #     _dict = {}

    #     if x is not None and x in list(self.keys()):
    #         _dict['x'] = self.data[x]
    #     elif x is not None:
    #         _dict['x'] = x
    #     else:
    #         pass

    #     if y is not None and y in list(self.keys()):
    #         _dict['y'] = self.data[y]
    #     elif y is not None:
    #         _dict['y'] = y
    #     else:
    #         pass

    #     if size is not None and size in list(self.keys()):
    #         _dict['size'] = self.data[size]
    #     elif size is not None:
    #         _dict['size'] = [size] * _n
    #     else:
    #         pass

    #     if color is not None and color in list(self.keys()):
    #         _dict['color'] = self.data[color]
    #     elif color is not None:
    #         _dict['color'] = [color] * _n
    #     else:
    #         pass

    #     if marker is not None and marker in list(self.keys()):
    #         _dict['marker'] = self.data[marker]
    #     elif marker is not None:
    #         _dict['marker'] = [marker] * _n
    #     else:
    #         pass

    #     if legend_group is not None and legend_group in list(self.keys()):
    #         _dict['legend_group'] = self.data[legend_group]
    #     elif legend_group is not None:
    #         _dict['legend_group'] = [legend_group] * _n
    #     else:
    #         pass

    #     _dict['mask'] = self.mask

    #     return _dict

class DataSourceStyle:
    from bokeh.models import DataTable
    def __init__(self,
                 data_sources: dict,
                 width: int | None = None,
                 height: int | None = None):
        """
        Provides a bokeh table that can be used to control the style of how the different DataSources are plotted

        :param data_sources:
            dictionary of DataSource's
            Same as in CrossPlotter
        :param width:
        :param height:
        """
        if width is None:
            width = 600
        self.width = width
        if height is None:
            height = 200
        self.height = height
        self.keys = ['name', 'color', 'marker', 'size', 'opacity', 'order']
        self.names = list(data_sources.keys())

        # fill the original cds with default values
        _dict = {_key: [] for _key in self.keys}
        for _i, _name in enumerate(self.names):
            _dict['name'].append(_name)
            _dict['color'].append(cnames[_i % len(cnames)])
            _dict['marker'].append(markers[_i % len(markers)])
            _dict['size'].append(5.)
            _dict['opacity'].append(1.)
            _dict['order'].append(_i)
        self._cds = ColumnDataSource(_dict)

    @property
    def cds(self) -> ColumnDataSource:
       return self._cds

    def table_columns(self):
        from bokeh.models import (SelectEditor, StringEditor, TableColumn, IntEditor, HTMLTemplateFormatter)
        colored_cell_template = """
                <div style="background:<%= 
                    (function color_from_val(){
                        return(color)
                        }()) %>; 
                    color: white"> 
                <%= value %>
                </div>
            """
        formatter = HTMLTemplateFormatter(template=colored_cell_template)

        table_columns = [
            TableColumn(field='name', title='Name', editor=SelectEditor(options=self.names)),
            TableColumn(field='color', title='Color', editor=StringEditor(), formatter=formatter),
            TableColumn(field='marker', title='Marker', editor=SelectEditor(options=markers)),
            TableColumn(field='size', title='Size', editor=SelectEditor(options=['1', '5', '10', '15', '20', '30', 'Size'])),
            TableColumn(field='opacity', title='Opacity', editor=SelectEditor(options=['0.2', '0.4', '0.6', '0.8', '1.0']))
            # TableColumn(field='order', title='Order', editor=IntEditor(step=1))
        ]
        return table_columns

    def draw(self,
             cds: ColumnDataSource):
        """
        Returns a table

        :param cds:
            ColumnDataSource
            Source for style used for plotting data
        :return:
        """
        from bokeh.models import DataTable, Div
        from bokeh.plotting import column

        title = Div(text =
                    """
                    <div style="font-size:12px; font-weight:600; margin-bottom:0px; text-align:center">
                        Data source styles
                    </div>
               """)

        dt = DataTable(
            source=cds,
            columns=self.table_columns(),
            editable=True,
            width=self.width,
            height=self.height,
            index_position=-1,
            index_header='index'
        )

        return column(title, dt, sizing_mode='stretch_width')


class CrossPlotter:
    """
    Class for holding the cross plot

        # Intended usage
    > data_sources = ...  # See DataSource for explanation
    > xp = CrossPlotter(data_sources)
    > cds = xp.cds()
        # Now you can add any additional functionality to control the cds
    > xplot, x_menu, y_menu, size_menu, ... = xp.draw(cds)
        # Now you can show and draw the xplot and the different menus

    """
    def __init__(self,
                 data_sources: dict,
                 x: str | None = None,
                 y: str | None = None,
                 working_intervals: Intervals | None = None,
                 cutoffs: Cutoffs | None = None,
                 width: int | None = None,
                 height: int | None = None,
                 tools: list | None = None):
        """

        :param data_sources:
            dictionary of DataSource's
            All variables within one DataSource have the same length
            The same variable name can be reused across DataSource's
        :param x:
            str
            Name of the X variable
        :param y:
            str
            Name of the Y variable
        :param working_intervals:
            Intervals
            Object containing the working intervals
        :param cutoffs:
            Cutoffs
            Object containing the rules used for masks and classification
        :param width:
            int
        :param height:
            int
        :param tools:
        """

        self._data_sources = data_sources
        if x is None:
            x = self.common_variables[0]
        if x not in self.common_variables:
            raise IOError('The x parameter {} is not among the parameters of the source ({})'.format(
                x, ', '.join(self.common_variables) ))
        if y is None:
            y = self.common_variables[1]
        if y not in self.common_variables:
            raise IOError('The y parameter {} is not among the parameters of the source ({})'.format(
                y, ', '.join(self.common_variables) ))
        if width is None:
            width = 600
        if height is None:
            height = 600
        self.width = width
        self.height = height
        self.x = x
        self.y = y
        # if data_sources is not None:
        #     self._sources = {_key: _val.source for _key, _val in data_sources.items()}
        # else:
        #     self._sources = None
        self.xplot = None
        self.cutoffs = cutoffs
        self._cutoffs_table = None
        if self.cutoffs is not None:
            self._cutoffs_table = ClassificationTable(rules=self.cutoffs.cutoffs)
        self.active_cutoffs = []

        self.working_intervals = working_intervals
        self._interval_table = None
        if self.working_intervals is not None:
            self._interval_table = WorkingIntervalsTable(self.working_intervals, set_all_active=False)
        self.active_intervals = []


        if tools is None:
            tools = default_tools
        self._tools = tools

        self.fixed_sizes = ['1', '5', '10', '20']
        self.fixed_colors = ['Data set', 'Classification']

    def __len__(self):
        _len = 0
        for _key, _item in self._data_sources.items():
            _var = self.common_variables[0]
            _len += len(_item.cds.data[_var])
        return _len

    @property
    def cutoffs_table(self):
        return self._cutoffs_table

    @property
    def interval_table(self):
        return self._interval_table

    @property
    def all_variables(self):
        _all = []
        for _source in self._data_sources.values():
            _all += [_x for _x in list(_source.keys()) if _x != 'mask']
        return list(set(_all))

    @property
    def templates(self):
        _all = {}
        for _source in self._data_sources.values():
            for _key, _val in _source.templates.items():
                # Avoid incomplete templates
                if _val is None or list(_val.dict().keys())[0] is None:
                    continue
                _all[_key] = _val
        return _all

    @property
    def common_variables(self):
        _list =  list(set.intersection(
            *[set(list(_s.keys())) for _s in self._data_sources.values()]
        ))
        if 'mask' in _list:
            _list.remove('mask')
        return _list

    @property
    def common_units(self):
        _units = []
        _params = []
        for _param in self.common_variables:
            # The 'parameter' mask is typically not specified in the templates
            if _param == 'mask':
                _units.append('')
                continue
            _units.append(
                self.templates[_param].units if _param in self.templates else ''
            )
        return _units

    @property
    def cds(self) -> ColumnDataSource:
        """
        Returns a merged CDS with all the common variables from all data_sources, plus the extra variables
        created by add_x_y_to_cds
        :return:
        """
        _dict = {}
        _i = 0
        for _key, _item in self._data_sources.items():
            _len = 0
            for _var in self.common_variables:
                _len = len(_item.cds.data[_var])
                if _i == 0:
                    _dict[_var] = _item.cds.data[_var]
                else:
                    _dict[_var] = np.append(_dict[_var], _item.cds.data[_var])
            if _i == 0:
                _dict['source_name'] = np.array([_key] * _len)
                _dict['legend_group'] = np.array([_key] * _len)
                _dict['color'] = np.array([cnames[_i % len(cnames)]] * _len)
                _dict['marker'] = np.array([markers[_i % len(markers)]] * _len)
                _dict['size'] = np.array([5.] * _len)
                _dict['opacity'] = np.array([1.] * _len)
                _dict['mask'] = np.array([True] * _len)
            else:
                _dict['source_name'] = np.append(_dict['source_name'], np.array([_key] * _len))
                _dict['legend_group'] = np.append(_dict['legend_group'], np.array([_key] * _len))
                _dict['color'] = np.append(_dict['color'], np.array([cnames[_i % len(cnames)]] * _len))
                _dict['marker'] = np.append(_dict['marker'], np.array([markers[_i % len(markers)]] * _len))
                _dict['size'] = np.append(_dict['size'], np.array([5.] * _len))
                _dict['opacity'] = np.append(_dict['opacity'], np.array([1.] * _len))
                _dict['mask'] = np.append(_dict['mask'], np.array([True] * _len))
            _i += 1

        _dict = add_x_y_to_cds(_dict, self.x, self.y)
        return ColumnDataSource(_dict)

    # def x_y_source(self,
    #                source_dict: dict,
    #                x: None | str = None,
    #                y: None | str = None,
    #                size: None | float | str = None,
    #                color: None | str = None,
    #                marker: None | str = None,
    #                legend_group: None | str = None,
    #                mask: None | np.ndarray = None
    #                ) -> dict:
    #     """
    #     The idea is to let the input decide which parameter that should be used on the x-axis, y-axis, size, color,
    #     marker and legend
    #     E.G.
    #         if x = 'vp'
    #         WHEN
    #         source_dict = dict(vp=..., vs=..., rho=...)
    #         THEN
    #         x_y_source = dict(x=source_dict['vp'], y=..., etc...)

    #     :param source_dict:
    #     :param x:
    #     :param y:
    #     :param size:
    #     :param color:
    #     :param marker:
    #     :param legend_group:
    #     :param mask:

    #     :return:
    #         dict
    #         transformed_source
    #         The dictionary has at least the following keys:
    #             'x', 'y', 'size', 'color', 'marker' and 'legend_group'
    #     """
    #     _n = len(self)
    #     _vars = list(source_dict.keys())
    #     _dict = {}

    #     if x is not None and x in _vars:
    #         _dict['x'] = source_dict[x]
    #     elif x is not None:
    #         _dict['x'] = x
    #     else:
    #         pass

    #     if y is not None and y in _vars:
    #         _dict['y'] = source_dict[y]
    #     elif y is not None:
    #         _dict['y'] = y
    #     else:
    #         pass

    #     if size is not None and size in _vars:
    #         _dict['size'] = source_dict[size]
    #     elif size is not None:
    #         _dict['size'] = [size] * _n
    #     else:
    #         _dict['size'] = source_dict['size']

    #     if color is not None and color in _vars:
    #         _dict['color'] = source_dict[color]
    #     elif color is not None:
    #         _dict['color'] = [color] * _n
    #     else:
    #         _dict['color'] = source_dict['color']

    #     if marker is not None and marker in _vars:
    #         _dict['marker'] = source_dict[marker]
    #     elif marker is not None:
    #         _dict['marker'] = [marker] * _n
    #     else:
    #         _dict['marker'] = source_dict['marker']

    #     if legend_group is not None and legend_group in _vars:
    #         _dict['legend_group'] = source_dict[legend_group]
    #     elif legend_group is not None:
    #         _dict['legend_group'] = [legend_group] * _n
    #     else:
    #         _dict['legend_group'] = source_dict['legend_group']

    #     if mask is not None:
    #         _dict['mask'] = mask
    #     else:
    #         _dict['mask'] = source_dict['mask']

    #     _dict['source_name'] = source_dict['source_name']
    #     return _dict

    def js_code(self, console_only=False):
        console_only_code = """
            const x_param = x_drop.value;
            console.log('dropdown: ' + cb_obj.value, x_param);
        """
        code1 = """
            const x_param = x_drop.value;
            const y_param = y_drop.value;
            const s_param = s_drop.value;
            //const c_param = c_drop.value;
            //const m_param = m_drop.value;
            //const l_param = l_drop.value;
            const min = min_max[s_param][0];
            const max = min_max[s_param][1];
            const s = [];
            function size(arr1) {
                let s = [];
                for (let i = 0; i < arr1.length; i++) {
                  s.push(10 + 70 * (arr1[i] - min) / (max - min));
                      }
                return s;
            }
            // REPLACE DATA
            for (let i = 0; i < data_keys.length; i++) {
                data_sources[i].data['x'] = orig_data_sources[i].data[x_param];
                data_sources[i].data['y'] = orig_data_sources[i].data[y_param]
                if (min_max[s_param][0] === 'constant') {
                        let length = orig_data_sources[i].data[x_param].length;
                        data_sources[i].data['size'] = Array(length).fill(Number(s_param));
                    } else {
                        data_sources[i].data['size'] = size(orig_data_sources[i].data[s_param]);
                    }
                }
            //
            for (let i = 0; i < data_keys.length; i++) {
                data_sources[i].change.emit();
                }

            // X AXIS
            xaxis.axis_label = x_param;
            if (templates[x_param]['min'] === null || templates[x_param]['min'] === undefined) {
                    console.log('No ' + x_param + ' min value. Use min: ' + min_max[x_param][0]);
                    x_range.start = min_max[x_param][0];
                } else {
                    console.log(x_param + ' min value ' + templates[x_param]['min']);
                    x_range.start = templates[x_param]['min'];
                }
            if (templates[x_param]['max'] === null || templates[x_param]['max'] === undefined) {
                    console.log('No ' + x_param + ' max value. Use max: ' + min_max[x_param][1]);
                    x_range.end = min_max[x_param][1];
                } else {
                    console.log(x_param + ' max value ' + templates[x_param]['max']);
                    x_range.end = templates[x_param]['max'];
                }
            x_range.change.emit()

            // Y AXIS
            yaxis.axis_label = y_param;
            if (templates[y_param]['min'] === null || templates[y_param]['min'] === undefined) {
                    console.log('No ' + y_param + ' min value. Use min: ' + min_max[y_param][0]);
                    y_range.start = min_max[y_param][0];
                } else {
                    console.log(y_param + ' min value ' + templates[y_param]['min']);
                    y_range.start = templates[y_param]['min'];
                }
            if (templates[y_param]['max'] === null || templates[y_param]['max'] === undefined) {
                    console.log('No ' + y_param + ' max value. Use max: ' + min_max[y_param][1]);
                    y_range.end = min_max[y_param][1];
                } else {
                    console.log(y_param + ' max value ' + templates[y_param]['max']);
                    y_range.end = templates[y_param]['max'];
                }
            y_range.change.emit()

            title.text = 'XXX';
            //
            console.log('dropdown: ' + cb_obj.value, x_param);
            """
        code2 = """
            const x_param = x_drop.value;
            const y_param = y_drop.value;
            const s_param = s_drop.value;
            //const c_param = c_drop.value;
            //const m_param = m_drop.value;
            //const l_param = l_drop.value;
            const min = min_max[s_param][0];
            const max = min_max[s_param][1];
            const s = [];
            function size(arr1) {
                let s = [];
                for (let i = 0; i < arr1.length; i++) {
                  s.push(10 + 70 * (arr1[i] - min) / (max - min));
                      }
                return s;
            }
            // REPLACE DATA
            x_y_source.data['x'] = source.data[x_param];
            x_y_source.data['y'] = source.data[y_param];
            if (min_max[s_param][0] === 'constant') {
                    let length = source.data[x_param].length;
                    x_y_source.data['size'] = Array(length).fill(Number(s_param));
                } else {
                    x_y_source.data['size'] = size(source.data[s_param]);
                }
            //
            x_y_source.change.emit();

            // X AXIS
            xaxis.axis_label = x_param;
            if (templates[x_param]['min'] === null || templates[x_param]['min'] === undefined) {
                    console.log('No ' + x_param + ' min value. Use min: ' + min_max[x_param][0]);
                    x_range.start = min_max[x_param][0];
                } else {
                    console.log(x_param + ' min value ' + templates[x_param]['min']);
                    x_range.start = templates[x_param]['min'];
                }
            if (templates[x_param]['max'] === null || templates[x_param]['max'] === undefined) {
                    console.log('No ' + x_param + ' max value. Use max: ' + min_max[x_param][1]);
                    x_range.end = min_max[x_param][1];
                } else {
                    console.log(x_param + ' max value ' + templates[x_param]['max']);
                    x_range.end = templates[x_param]['max'];
                }
            x_range.change.emit()

            // Y AXIS
            yaxis.axis_label = y_param;
            if (templates[y_param]['min'] === null || templates[y_param]['min'] === undefined) {
                    console.log('No ' + y_param + ' min value. Use min: ' + min_max[y_param][0]);
                    y_range.start = min_max[y_param][0];
                } else {
                    console.log(y_param + ' min value ' + templates[y_param]['min']);
                    y_range.start = templates[y_param]['min'];
                }
            if (templates[y_param]['max'] === null || templates[y_param]['max'] === undefined) {
                    console.log('No ' + y_param + ' max value. Use max: ' + min_max[y_param][1]);
                    y_range.end = min_max[y_param][1];
                } else {
                    console.log(y_param + ' max value ' + templates[y_param]['max']);
                    y_range.end = templates[y_param]['max'];
                }
            y_range.change.emit()

            title.text = 'XXX';
            //
            console.log('dropdown: ' + cb_obj.value, x_param);
            """
        code3 = """
            const x_param = x_drop.value;
            const y_param = y_drop.value;
            const s_param = s_drop.value;
            //const c_param = c_drop.value;
            //const m_param = m_drop.value;
            //const l_param = l_drop.value;
            const min = min_max[s_param][0];
            const max = min_max[s_param][1];
            const s = [];
            var new_data = x_y_source.data;
            
            function size(arr1) {
                let s = [];
                for (let i = 0; i < arr1.length; i++) {
                  s.push(10 + 70 * (arr1[i] - min) / (max - min));
                      }
                return s;
            }
            // REPLACE DATA
            new_data['x'] = x_y_source.data[x_param];
            new_data['y'] = x_y_source.data[y_param];
            if (min_max[s_param][0] === 'constant') {
                    let length = x_y_source.data[x_param].length;
                    x_y_source.data['size'] = Array(length).fill(Number(s_param));
                } else {
                    x_y_source.data['size'] = size(x_y_source.data[s_param]);
                }
            //
            x_y_source.change.emit();
                
            // X AXIS
            xaxis.axis_label = x_param;
            if (templates[x_param]['min'] === null || templates[x_param]['min'] === undefined) {
                    console.log('No ' + x_param + ' min value. Use min: ' + min_max[x_param][0]);
                    x_range.start = min_max[x_param][0];
                } else {
                    console.log(x_param + ' min value ' + templates[x_param]['min']);
                    x_range.start = templates[x_param]['min'];
                }
            if (templates[x_param]['max'] === null || templates[x_param]['max'] === undefined) {
                    console.log('No ' + x_param + ' max value. Use max: ' + min_max[x_param][1]);
                    x_range.end = min_max[x_param][1];
                } else {
                    console.log(x_param + ' max value ' + templates[x_param]['max']);
                    x_range.end = templates[x_param]['max'];
                }
            x_range.change.emit()
            
            // Y AXIS
            yaxis.axis_label = y_param;
            if (templates[y_param]['min'] === null || templates[y_param]['min'] === undefined) {
                    console.log('No ' + y_param + ' min value. Use min: ' + min_max[y_param][0]);
                    y_range.start = min_max[y_param][0];
                } else {
                    console.log(y_param + ' min value ' + templates[y_param]['min']);
                    y_range.start = templates[y_param]['min'];
                }
            if (templates[y_param]['max'] === null || templates[y_param]['max'] === undefined) {
                    console.log('No ' + y_param + ' max value. Use max: ' + min_max[y_param][1]);
                    y_range.end = min_max[y_param][1];
                } else {
                    console.log(y_param + ' max value ' + templates[y_param]['max']);
                    y_range.end = templates[y_param]['max'];
                }
            y_range.change.emit()
            
            title.text = 'XXX';
            //
            console.log('dropdown: ' + cb_obj.value, x_param);
            x_y_source.data = new_data;
            """
        if console_only:
            return console_only_code
        else:
            return code3

    def drop_down_menus(self):
        from bokeh.models import Select
        _x_menu =  Select(title='X axis', value=self.x, options=self.common_variables)
        _y_menu =  Select(title='Y axis', value=self.y, options=self.common_variables)
        _size_menu =  Select(title='Size', value=20,
                             options= self.fixed_sizes + self.common_variables)
        # TODO The selectors below needs fixing before they can be used properly
        _color_menu =  Select(title='Color axis', value=self.common_variables[0],
                              options=self.fixed_colors + self.common_variables)
        _marker_menu =  Select(title='Marker', value=self.common_variables[0], options=self.common_variables)
        _legend_menu =  Select(title='Legend', value=self.common_variables[0], options=self.common_variables)
        return _x_menu, _y_menu, _size_menu, _color_menu, _marker_menu, _legend_menu

    def min_and_max(self):
        _out = {}
        for _key in self.all_variables:
            _min = 1E6; _max = -1E6
            for _source in self._data_sources.values():
                if _key not in list(_source.keys()):
                    continue
                if _source.min_and_max()[_key][0].magnitude < _min:
                    _min = _source.min_and_max()[_key][0].magnitude
                if _source.min_and_max()[_key][1].magnitude > _max:
                    _max = _source.min_and_max()[_key][1].magnitude
            _out[_key] = [_min, _max]
        for _key in self.fixed_sizes:
            _out[_key] = ['constant', 'constant']
        return _out

    def add_data_source_style(self, cds: ColumnDataSource):
        code = """
            const x_data = x_source.data;
            const style_data = style_source.data;
            var orig_order = orig_order;
            const cols = Object.keys(style_data);
            const nrows = style_data[cols[0]].length;
            const groups = x_data['legend_group'];
            // const indices = Array.from(Array(groups.length).keys());
            const size_string = "Size";
            
            console.log('Trying to update style in plot')
            
            // Update the colors, markers and sizes based on the style table
            // Iterate over all lines in the settings table
            for (let i = 0; i < nrows; i++) {
                //console.log(style_data['name'][i], style_data['color'][i], style_data['marker'][i], style_data['size'][i]) 
                // iterate over all points in the x-plot
                for (let j = 0; j < groups.length; j++) {
                    if (x_data['legend_group'][j] === style_data['name'][i]) {
                        x_data['color'][j] = style_data['color'][i];
                        x_data['marker'][j] = style_data['marker'][i];
                        if (String(style_data['size'][i]) !== size_string) {
                            x_data['size'][j] = style_data['size'][i];
                        }
                        x_data['opacity'][j] = style_data['opacity'][i];
                    }
                }
            }
            
            //  // Look for changes in the order, and re order the data
            //  let changed = false;
            //  for (let i = 0; i < nrows; i++) {
            //      if (orig_order[i] !== style_data['order'][i]) {
            //          console.log('Order has been changed')
            //          changed = true;
            //          orig_order[i] = style_data['order'][i];
            //      }
            //  }
            //  if (changed) {
            //          console.log('Change in order has been detected')
            //          indices.sort((a, b) => style_data['order'][a] - style_data['order'][b]);
            //          const new_data = {};
            //          for (const key in x_data) {
            //              new_data[key] = indices.map(i => x_data[key][i]);
            //          }
            //          x_source.data = new_data;
            //  }
            x_source.change.emit()
            
        """
        # TODO
        # The above 'order' function works, but Bokeh draws everything in one 'vectorized call', making the
        # order meaningless
        # A suggested solution by CoPilot is to split the data into different renderers, and then control
        # each of them individually:
        """
        # Create one renderer per group
        renderers = {}

        for group in df['group'].unique():
            view = ColumnDataSource(df[df['group'] == group])

            r = p.scatter(
                x='x',
                y='y',
                source=view,
                size='size',
                color='color',
                marker='marker',
                legend_label=group
            )

            renderers[group] = r
            
        # Then, the JS call back:
        const renderers = renderer_dict;
        const selected = group_select.value;

        // Move selected renderer to end (top layer)
        const all_renderers = Object.values(renderers);

        // Remove selected
        const others = all_renderers.filter(r => r !== renderers[selected]);

        // Rebuild order
        p.renderers = [...others, renderers[selected]];
        ``
        """
        style_table = DataSourceStyle(self._data_sources)
        style_cds = style_table.cds
        orig_order = style_cds.data['order']
        source_callback = CustomJS(args=dict(x_source=cds, style_source=style_cds, orig_order=orig_order), code=code)
        style_cds.js_on_change('patching', source_callback)

        return style_table.draw(style_cds)

    def fig(self) -> figure:
        xplot = figure(width=self.width, height=self.height, tools=self._tools)
        xplot.toolbar.active_inspect = None
        xplot.toolbar.logo = None
        return xplot

    def draw(self, cds: ColumnDataSource, set_all_intervals_active: bool = False, verbose: bool = False):
        from bokeh.models import CDSView, BooleanFilter, Button, Div
        import blixt_geo_py.utils.masks as masks
        from blixt_geo_py import Q_

        self.xplot = self.fig()

        # set up drop down menus
        x_menu, y_menu, size_menu, color_menu, marker_menu, legend_menu = self.drop_down_menus()
        # Make non-working menus inactive
        color_menu.disabled = True
        marker_menu.disabled = True
        legend_menu.disabled = True


        # Determine x and y variable
        x_var = x_menu.value
        y_var = y_menu.value
        size_var = size_menu.value

        # Draw the classification / cutoffs table
        ct_cds = None
        if self.cutoffs_table is not None:
            ct_cds = self.cutoffs_table.cds
            ct_guis = self.cutoffs_table.draw(ct_cds, self.common_variables, self.common_units, verbose=verbose)
            # ct_guis = table, table_buttons
        else:
            ct_guis = [Div(text='', width=10, height=10)]*2

        # Draw the working intervals table
        wis_cds = None
        if self.interval_table is not None:
            wis_cds = self.interval_table.cds
            wis_guis = self.interval_table.draw(wis_cds, verbose=verbose)
        else:
            wis_guis = Div(text='', width=10, height=10)

        # Create a BooleanFilter using the 'mask' column
        boolean_filter = BooleanFilter(booleans=cds.data['mask'])

        # Create a CDSView using the BooleanFilter
        view = CDSView(filter=boolean_filter)

        self.xplot.scatter(x='x', y='y', source=cds, view=view, fill_color='color', marker='marker',
                      legend_group='legend_group', size='size', fill_alpha='opacity', line_color=None)

        # Axes
        for _var, _axis in zip([x_var, y_var], [self.xplot.xaxis, self.xplot.yaxis]):
            # _axis.axis_label_text_font_size = '10px'
            # _axis.major_label_text_font_size = '10px'
            _axis.axis_label_standoff = 0
            if _var not in list(self.templates.keys()):
                continue
            _axis.axis_label = '{} [{}]'.format(
                self.templates[_var].name, self.templates[_var].units)
        for _var, _range in zip([x_var, y_var], [self.xplot.x_range, self.xplot.y_range]):
            if _var not in list(self.templates.keys()):
                continue
            if self.templates[_var].min is not None:
                _range.start = self.templates[_var].min
            if self.templates[_var].max is not None:
                _range.end = self.templates[_var].max

        # Legend
        if len(self.xplot.legend) > 0:
            self.xplot.legend.click_policy = 'hide'
            self.xplot.legend.location = 'top_right'
            # self.xplot.legend.label_text_font_size = '8pt'

        #
        # Arrange call backs
        #

        # # Try to remove incomplete templates
        # incomplete = []
        # for _key, _val in self.templates.items():
        #     if _val is not None and list(_val.dict().keys())[0] is None:
        #         print(_key, type(_val), len(list(_val.dict().keys())), list(_val.dict().keys()))
        #         incomplete.append(_key)

        # for _key in incomplete:
        #             self.templates.__delitem__(_key)
        # print(self.templates.keys())

        args_dict = dict(x_drop=x_menu,
                         y_drop=y_menu,
                         s_drop=size_menu,
                         x_range=self.xplot.x_range,
                         y_range=self.xplot.y_range,
                         templates={_key: _val.dict()[_key] for _key, _val in self.templates.items() if _val is not None},
                         # data_keys=[_key for _key in list(sources.keys())],
                         # data_sources=[_val for _val in list(sources.values())],
                         # orig_data_sources=[_val.source for _val in list(self._data_sources.values())],
                         x_y_source=cds,
                         source=self.cds,
                         min_max=self.min_and_max(),
                         # # cmap=exp_cmap,
                         title=self.xplot.title,
                         xaxis=self.xplot.xaxis[0],
                         yaxis=self.xplot.yaxis[0],
                         # # bar=bar
                         )

        x_menu.js_on_change(
            'value',
            CustomJS(
                args=args_dict,
                code=self.js_code(console_only=False)))
        # # Update self.x   DIDN'T WORK
        # x_menu.js_on_change('value', CustomJS(args=dict(x_drop=x_menu, x=self.x),
        #                                       code= """ const x_param = x_drop.value;
        #                                         x = x_param; """))

        y_menu.js_on_change(
            'value',
            CustomJS(
                args=args_dict,
                code=self.js_code()))
        # y_menu.js_on_change('value', CustomJS(args=dict(y_drop=y_menu, y=self.y),
        #                                       code= """ const y_param = y_drop.value;
        #                                         console.log('TEST', y_param)
        #                                         y = y_param; """))

        size_menu.js_on_change(
            'value',
            CustomJS(
                args=args_dict,
                code=self.js_code()))

        cds.js_on_change('patching', CustomJS(
            args=dict(source=cds),
            code="""
            console.log('Patching event detected in CrossPlotter');
            """
        ))

        data_change_callback = CustomJS(
            args=dict(source=cds, filter=boolean_filter),
            code="""
            const new_filter = source.data['mask'];
            filter.booleans = new_filter;
            console.log('Data event detected in CrossPlotter');
            """
        )

        def apply_mask_function():
            if self.cutoffs_table is not None and ct_cds is not None:
                _mask_ct = self.cutoffs_table.create_mask(ct_cds, cds, verbose=True)
                self.active_cutoffs = self.cutoffs_table.active_cutoffs(ct_cds)
            else:
                _mask_ct = np.ones(len(cds.data['mask']), dtype=bool)

            if self.interval_table is not None and wis_cds is not None:
               _mask_wis = self.interval_table.create_mask(
                   wis_cds,
                   Q_(cds.data['md'], 'm'),
                   list(cds.data['source_name']),
                   verbose=True)
               self.active_intervals = self.interval_table.active_intervals(wis_cds)
            else:
                _mask_wis = np.ones(len(cds.data['mask']), dtype=bool)

            cds.data['mask'] = masks.combine_masks([_mask_ct, _mask_wis])

        apply_mask = Button(label='Apply masks', button_type='success')
        apply_mask.on_click(apply_mask_function)
        apply_mask.js_on_click(CustomJS(
            args=dict(cb2=data_change_callback),
            code="""
                cb2.execute();
            """
        ))

        reset_mask = Button(label='Reset mask', button_type='success')
        reset_mask.js_on_click(CustomJS(
            args=dict(source=cds, cb2=data_change_callback),
            code = """
                var _data = source.data;
                console.log('Mask is reset');
                for (let j = 0; j < _data['mask'].length; j++) {
                    _data['mask'][j] = true;
                }
                source.data = _data;
                cb2.execute();
            """
        ))
        # This is a test to see if reset_mask can update the plot, and with this extra call it did
        reset_mask.js_on_click(CustomJS(args=args_dict, code=self.js_code()))

        cds.js_on_change('data', data_change_callback)

        return self.xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis

    def show_plot(self, cds, out_file):
        # This is a short cut to give a quick view of the cross plot
        from bokeh.io import output_file
        output_file(out_file)
        xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = self.draw(cds)
        style_table = self.add_data_source_style(cds)
        show(
            row(
                column(
                    xplot,
                    row(x_menu, y_menu, size_menu, color_menu, reset_mask)
                ),
                column(style_table)
            )
        )
