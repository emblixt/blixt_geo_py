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
from bokeh.models import PanTool, BoxZoomTool, WheelZoomTool, ResetTool, SaveTool, CrosshairTool, HoverTool
from bokeh.models import ColumnDataSource, CustomJS, Range1d
from bokeh.plotting import column, row
from bokeh.plotting import figure, show

from blixt_geo_py.core.core import Intervals, WorkingIntervalsTable
from blixt_geo_py.core.core import Cutoffs, ClassificationTable, LogTable
from blixt_geo_py.utils.utils import print_info

logger = logging.getLogger(__name__)

def default_tools() -> list:
    """
    Returns a new set of the default tools for each call. A bokeh model, like a tool, can only belong to one document,
    so reusing the same tools in a second plot raises "Models must be owned by only a single document"
    """
    return [
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
default_marker_size = 5.


def magnitude_in_units(values, units: pint.Unit | None, name: str = '') -> np.ndarray:
    """
    Returns the values as a plain array, ready for a ColumnDataSource, converted to the given units when possible

    :param values:
        pint Quantity or array-like
        Values without units are returned as they are
    :param units:
        pint Unit or None
        None means that a Quantity keeps its own units
    :param name:
        str
        Name of the variable, only used in the warning about incompatible units
    :return:
        np.ndarray
    """
    if not isinstance(values, pint.Quantity):
        return np.asarray(values)
    if units is None:
        return np.asarray(values.magnitude)
    try:
        return np.asarray(values.to(units).magnitude)
    except pint.DimensionalityError:
        print_info('Can not convert {} from {} to {}, keeping the values as they are'.format(
            name, values.units, units), 'warning', logger)
        return np.asarray(values.magnitude)


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

    def _column(value, default_key: str):
        if value is None:
            return cds_dict[default_key]
        if isinstance(value, str) and value in _vars:
            return cds_dict[value]
        return [value] * _n

    _dict = {
        'x': _column(x, _vars[0]),
        'y': _column(y, _vars[1]),
        'size': _column(size, 'size'),
        'color': _column(color, 'color'),
        'marker': _column(marker, 'marker'),
        'legend_group': _column(legend_group, 'legend_group'),
        'opacity': _column(opacity, 'opacity'),
        'mask': mask if mask is not None else cds_dict['mask'],
        'source_name': cds_dict['source_name']
    }

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
            # The 'mask' column has no units
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
        pass

class DataSourceStyle:
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
            _dict['size'].append(default_marker_size)
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
        _common = self.common_variables
        if len(_common) < 2:
            raise IOError('The data sources must have at least two variables in common, but they only share: {}'.format(
                ', '.join(_common) if _common else 'nothing'))
        if x is None:
            x = _common[0]
        if x not in _common:
            raise IOError('The x parameter {} is not among the parameters of the source ({})'.format(
                x, ', '.join(_common)))
        if y is None:
            y = next(_var for _var in _common if _var != x)
        if y not in _common:
            raise IOError('The y parameter {} is not among the parameters of the source ({})'.format(
                y, ', '.join(_common)))
        if width is None:
            width = 600
        if height is None:
            height = 600
        self.width = width
        self.height = height
        self.x = x
        self.y = y
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

        # None means that fig() creates a new set of the default tools for each plot, see default_tools()
        self._tools = tools

        self.fixed_sizes = ['1', '5', '10', '20']
        self.fixed_colors = ['Data set', 'Classification']

    def __len__(self):
        return sum(len(_item) for _item in self._data_sources.values())

    @property
    def cutoffs_table(self):
        return self._cutoffs_table

    @property
    def interval_table(self):
        return self._interval_table

    @property
    def all_variables(self):
        # dict.fromkeys removes duplicates, but keeps the order, which a set doesn't do between python sessions
        return list(dict.fromkeys(
            _x for _source in self._data_sources.values() for _x in _source.keys() if _x != 'mask'
        ))

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
        _sources = list(self._data_sources.values())
        # Keeps the order of the first data source, so the default x and y are the same each time
        return [_x for _x in _sources[0].keys()
                if _x != 'mask' and all(_x in _source.keys() for _source in _sources[1:])]

    @property
    def common_units(self):
        return [self.templates[_param].units if _param in self.templates else '' for _param in self.common_variables]

    @property
    def depth_variable(self) -> str | None:
        """
        Name of the common variable with the measured depth, which is named differently depending on the source of
        the data, e.g. 'dept' in las files. None if there is no such variable.
        """
        _common = self.common_variables
        return next((_var for _var in ['md', 'dept', 'depth'] if _var in _common), None)

    def plot_units(self, variable: str) -> pint.Unit | None:
        """
        Returns the units a variable is plotted in, which are the units of its template, as these are the units shown
        on the axes and in the cutoffs table. Without a usable template, the units of the first data source are used.

        :param variable:
            str
        :return:
            pint Unit or None
        """
        from blixt_geo_py import Q_
        _template = self.templates.get(variable)
        if _template is not None and _template.units:
            try:
                return Q_(1., _template.units).units
            except Exception:  # Units come from e.g. las files and can be any string, which pint raises many errors for
                logger.debug('Template of {} has unknown units: {}'.format(variable, _template.units))
        for _source in self._data_sources.values():
            if isinstance(_source.data.get(variable), pint.Quantity):
                return _source.data[variable].units
        return None

    @property
    def cds(self) -> ColumnDataSource:
        """
        Returns a merged CDS with all the common variables from all data_sources, plus the extra variables
        created by add_x_y_to_cds.
        Each variable is converted to the same units, see plot_units()
        :return:
        """
        _variables = self.common_variables
        _units = {_var: self.plot_units(_var) for _var in _variables}
        _columns = {_key: [] for _key in _variables + ['source_name', 'legend_group', 'color', 'marker', 'size',
                                                       'opacity', 'mask']}
        for _i, (_key, _item) in enumerate(self._data_sources.items()):
            for _var in _variables:
                _columns[_var].append(magnitude_in_units(_item.data[_var], _units[_var], _var))
            _len = len(_columns[_variables[0]][-1])
            _columns['source_name'].append(np.full(_len, _key))
            _columns['legend_group'].append(np.full(_len, _key))
            _columns['color'].append(np.full(_len, cnames[_i % len(cnames)]))
            _columns['marker'].append(np.full(_len, markers[_i % len(markers)]))
            _columns['size'].append(np.full(_len, default_marker_size))
            _columns['opacity'].append(np.full(_len, 1.))
            _columns['mask'].append(np.asarray(_item.data.get('mask', _item.mask), dtype=bool))

        _dict = {_key: np.concatenate(_val) for _key, _val in _columns.items()}
        _dict = add_x_y_to_cds(_dict, self.x, self.y)
        return ColumnDataSource(_dict)

    @staticmethod
    def js_code() -> str:
        """
        Code of the callback that updates the plot when one of the drop down menus is changed.
        The marker size is only updated by the size menu, so that changing the axes keeps the sizes set in the
        data source style table
        """
        return """
            const x_param = x_drop.value;
            const y_param = y_drop.value;
            const s_param = s_drop.value;
            // A new object is needed for bokeh to detect that the data has changed
            const new_data = {...x_y_source.data};

            new_data['x'] = new_data[x_param];
            new_data['y'] = new_data[y_param];

            if (cb_obj === s_drop) {
                const [min, max] = min_max[s_param];
                if (min === 'constant') {
                    new_data['size'] = Array(new_data[x_param].length).fill(Number(s_param));
                } else {
                    // Variables with a single value get the smallest size instead of dividing by zero
                    const scale = max > min ? 70 / (max - min) : 0;
                    new_data['size'] = Array.from(new_data[s_param], (value) => 10 + scale * (value - min));
                }
            }
            x_y_source.data = new_data;

            xaxis.axis_label = axis_labels[x_param];
            yaxis.axis_label = axis_labels[y_param];
            for (const [range, param] of [[x_range, x_param], [y_range, y_param]]) {
                const [start, end] = axis_limits[param];
                // Variables with no valid data have no limits
                if (start !== null && end !== null) {
                    range.start = start;
                    range.end = end;
                    // Where the reset tool returns to
                    range.reset_start = start;
                    range.reset_end = end;
                }
            }
            """

    def drop_down_menus(self):
        from bokeh.models import Select
        _common = self.common_variables
        _x_menu =  Select(title='X axis', value=self.x, options=_common)
        _y_menu =  Select(title='Y axis', value=self.y, options=_common)
        # The start value must be the size the data is drawn with, see the cds
        _size_menu =  Select(title='Size', value=str(int(default_marker_size)),
                             options= self.fixed_sizes + _common)
        _color_menu =  Select(title='Color axis', value=_common[0],
                              options=self.fixed_colors + _common)
        _marker_menu =  Select(title='Marker', value=_common[0], options=_common)
        _legend_menu =  Select(title='Legend', value=_common[0], options=_common)
        return _x_menu, _y_menu, _size_menu, _color_menu, _marker_menu, _legend_menu

    def min_and_max(self):
        """
        Returns the limits of each variable across all data sources, in the units of plot_units()
        Variables without any valid numbers get the limits [None, None]
        """
        _out = {}
        for _key in self.all_variables:
            _units = self.plot_units(_key)
            _min = None
            _max = None
            for _source in self._data_sources.values():
                if _key not in _source.keys():
                    continue
                _values = magnitude_in_units(_source.data[_key], _units, _key)
                if not np.issubdtype(_values.dtype, np.number):
                    continue
                _values = _values[np.isfinite(_values)]
                if _values.size == 0:
                    continue
                _min = float(_values.min()) if _min is None else min(_min, float(_values.min()))
                _max = float(_values.max()) if _max is None else max(_max, float(_values.max()))
            _out[_key] = [_min, _max]
        for _key in self.fixed_sizes:
            _out[_key] = ['constant', 'constant']
        return _out

    def axis_labels(self) -> dict:
        """
        Returns the axis label of each common variable
        """
        _labels = {}
        for _var in self.common_variables:
            _template = self.templates.get(_var)
            if _template is None:
                _labels[_var] = _var
            elif _template.units:
                _labels[_var] = '{} [{}]'.format(_template.name, _template.units)
            else:
                _labels[_var] = str(_template.name)
        return _labels

    def template_limits(self, variable: str) -> list:
        """
        Returns the [min, max] of the template of the variable, where each of them is None when not specified
        """
        _template = self.templates.get(variable)
        return [None, None] if _template is None else _template.plot_settings()[1]

    def axis_limits(self, min_max: dict | None = None) -> dict:
        """
        Returns the axis limits of each common variable, from its template or else from the data.
        Limits from the data get some padding, so that the outermost markers are not cut in half

        :param min_max:
            dict
            The result of min_and_max(), which is calculated when not given
        """
        if min_max is None:
            min_max = self.min_and_max()
        _limits = {}
        for _var in self.common_variables:
            _start, _end = self.template_limits(_var)
            _min, _max = min_max[_var]
            if _min is None:
                _limits[_var] = [_start, _end]
                continue
            # Variables with a single value also need a range that isn't empty
            _padding = 0.05 * (_max - _min) or 0.5
            _limits[_var] = [_min - _padding if _start is None else _start,
                             _max + _padding if _end is None else _end]
        return _limits

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
        style_table = DataSourceStyle(self._data_sources)
        style_cds = style_table.cds
        orig_order = style_cds.data['order']
        source_callback = CustomJS(args=dict(x_source=cds, style_source=style_cds, orig_order=orig_order), code=code)
        style_cds.js_on_change('patching', source_callback)

        return style_table.draw(style_cds)

    def fig(self) -> figure:
        tools = default_tools() if self._tools is None else self._tools
        xplot = figure(width=self.width, height=self.height, tools=tools)
        xplot.toolbar.active_inspect = None
        xplot.toolbar.logo = None
        return xplot

    def draw(self, cds: ColumnDataSource, set_all_intervals_active: bool = False, verbose: bool = False):
        from bokeh.models import CDSView, BooleanFilter, Button, Div, GroupFilter, IntersectionFilter
        import blixt_geo_py.utils.masks as masks
        from blixt_geo_py import Q_

        self.xplot = self.fig()

        # set up drop down menus
        x_menu, y_menu, size_menu, color_menu, marker_menu, legend_menu = self.drop_down_menus()
        # Make non-working menus inactive
        color_menu.disabled = True
        marker_menu.disabled = True
        legend_menu.disabled = True

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

        # Each data source has its own renderer, sharing the same cds and mask, because clicking on an item in the
        # legend hides all the renderers of that item
        scatter_renderers = []
        for _name in self._data_sources.keys():
            view = CDSView(filter=IntersectionFilter(operands=[
                boolean_filter, GroupFilter(column_name='source_name', group=str(_name))]))
            scatter_renderers.append(
                self.xplot.scatter(x='x', y='y', source=cds, view=view, fill_color='color', marker='marker',
                                   legend_label=str(_name), size='size', fill_alpha='opacity', line_color=None))

        # The default tooltips of the hover tool only show the position of the mouse
        if self._tools is None:
            _tooltips = [('Source', '@source_name'), ('x', '@x'), ('y', '@y')]
            if self.depth_variable is not None:
                _tooltips.append((self.depth_variable, '@{}'.format(self.depth_variable)))
            for _hover in self.xplot.select(type=HoverTool):
                _hover.tooltips = _tooltips
                _hover.renderers = scatter_renderers

        # Axes
        min_max = self.min_and_max()
        axis_labels = self.axis_labels()
        axis_limits = self.axis_limits(min_max)
        for _var, _axis in zip([x_menu.value, y_menu.value], [self.xplot.xaxis, self.xplot.yaxis]):
            # _axis.axis_label_text_font_size = '10px'
            # _axis.major_label_text_font_size = '10px'
            _axis.axis_label_standoff = 0
            _axis.axis_label = axis_labels[_var]
        # A Range1d, as the reset tool of a default DataRange1d always returns to the limits of the first variable.
        # Without any limits (no valid data, and no template) it is left to the DataRange1d
        if None not in axis_limits[x_menu.value]:
            self.xplot.x_range = Range1d(*axis_limits[x_menu.value])
        if None not in axis_limits[y_menu.value]:
            self.xplot.y_range = Range1d(*axis_limits[y_menu.value])

        # Legend
        if len(self.xplot.legend) > 0:
            self.xplot.legend.click_policy = 'hide'
            self.xplot.legend.location = 'top_right'
            # self.xplot.legend.label_text_font_size = '8pt'

        #
        # Arrange call backs
        #
        menu_callback = CustomJS(
            args=dict(x_drop=x_menu,
                      y_drop=y_menu,
                      s_drop=size_menu,
                      x_range=self.xplot.x_range,
                      y_range=self.xplot.y_range,
                      x_y_source=cds,
                      min_max=min_max,
                      axis_labels=axis_labels,
                      axis_limits=axis_limits,
                      xaxis=self.xplot.xaxis[0],
                      yaxis=self.xplot.yaxis[0]),
            code=self.js_code())
        for _menu in [x_menu, y_menu, size_menu]:
            _menu.js_on_change('value', menu_callback)

        if verbose:
            cds.js_on_change('patching', CustomJS(
                code="""
                console.log('Patching event detected in CrossPlotter');
                """
            ))

        data_change_callback = CustomJS(
            args=dict(source=cds, filter=boolean_filter),
            code="""
            // A new array is needed for bokeh to detect that the filter has changed
            filter.booleans = Array.from(source.data['mask'], Boolean);
            """
        )

        def apply_mask_function():
            if self.cutoffs_table is not None and ct_cds is not None:
                _mask_ct = self.cutoffs_table.create_mask(ct_cds, cds, verbose=verbose)
                self.active_cutoffs = self.cutoffs_table.active_cutoffs(ct_cds)
            else:
                _mask_ct = np.ones(len(cds.data['mask']), dtype=bool)

            _depth = self.depth_variable
            if self.interval_table is not None and wis_cds is not None and _depth is not None:
               _mask_wis = self.interval_table.create_mask(
                   wis_cds,
                   Q_(cds.data[_depth], self.plot_units(_depth) or 'm'),
                   list(cds.data['source_name']),
                   verbose=verbose)
               self.active_intervals = self.interval_table.active_intervals(wis_cds)
            else:
                if self.interval_table is not None:
                    print_info('Can not apply the working intervals, the data sources have no common depth variable',
                               'warning', logger)
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
            args=dict(source=cds),
            code = """
                // Assigning a new object triggers the data_change_callback
                source.data = {...source.data, mask: Array(source.data['mask'].length).fill(true)};
            """
        ))

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
