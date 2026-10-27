import matplotlib.pyplot as plt
import numpy as np
import logging
from matplotlib.ticker import (AutoMinorLocator, MultipleLocator)
import matplotlib.colors as mcolors
from itertools import cycle
import numbers

from blixt_geo_py.utils.definitions import def_lb_name

logger = logging.getLogger(__name__)

clrs = list(mcolors.BASE_COLORS.keys())
clrs.remove('w')
cclrs = cycle(clrs)  # "infinite" loop of the base colors


def next_color():
    return next(cclrs)


def set_up_column_plot(ax_names=None, width_ratios=None, height_ratios=None, fig_width=None, fig_height=None):
    """
    Sets yp a "column" plot, consisting of a header and log vs depth plot similar to what is seen in
    CPI plots
    :param ax_names:
        list
        list of names that are used to identify the different columns of the whole plot
    :param width_ratios:
    :param height_ratios:
    :param fig_width:
        int
    :param fig_height:
        int
    :return:
    fig, header_axes, plot_axes
    """
    n_rows = 2

    if ax_names is None:
        ax_names = ['main']
    if isinstance(ax_names, str):
        ax_names = list(ax_names)
    if width_ratios is None:
        width_ratios = [1] * len(ax_names)
    if isinstance(width_ratios, numbers.Number):
        width_ratios = [width_ratios] * len(ax_names)
    if len(ax_names) != len(width_ratios):
        raise IOError('Length of ax_names ({}) and width_ratios ({}) does not match'.format(
            len(ax_names), len(width_ratios)))

    n_cols = len(ax_names)

    if height_ratios is None:
        height_ratios = [1, 5]
    if fig_height is None:
        fig_height = 10
    if fig_width is None:
        if n_cols < 6:
            fig_width = n_cols * 3
        else:
            fig_width = n_cols * 2.5

    fig = plt.figure(figsize=(fig_width, fig_height))
    spec = fig.add_gridspec(nrows=n_rows, ncols=n_cols,
                            height_ratios=height_ratios, width_ratios=width_ratios,
                            hspace=0., wspace=0.,
                            left=0.05, bottom=0.03, right=0.98, top=0.96)
    header_axes = {}
    plot_axes = {}
    for i in range(len(ax_names)):
        header_axes[ax_names[i]] = fig.add_subplot(spec[0, i])
        plot_axes[ax_names[i]] = fig.add_subplot(spec[1, i])
    return fig, header_axes, plot_axes


# TODO: This uses the old Well object. Needs to be updated to the new
def plot_one_column(well, try_these_log_types, templates, header_ax=None, plot_ax=None, z_min=None, z_max=None,
                    block_name=None, mask=None, fill_betweens=None):
    """

    :param well:
        well object
    :param try_these_log_types:
        list
        list of log types, e.g. try_these_log_types = ['Saturation', 'Porosity'] which we will try to plot
        in this column plot
    :param templates:
        dict
        Dictionary of different templates as returned from Project().load_all_templates()
    :param header_ax:
        axis object
        Where the header will be plotted
    :param plot_ax:
        axis object
        Where the data will be plotted
    :param z_min & z_max
        Min and max value of the depth parameter
    :param fill_betweens:
        list
        list of triplets (logtype 1, logtype 2, color) which determines the fill_between color when logtype 1 is plotted
         to the right of logtype 2 (logtype 1 is not necessarily larger than logtype 2, but plots to the right of
         logtype 2 given the limits in the templates
         E.G. [('Density', 'Neutron density', 'b'), ('Neutron density', 'Density', 'y')]

         TODO
         fill_between only work when the templates of the data to plot contain min and max value limits
    :return:
    """
    if header_ax is None and plot_ax is None:
        fig, h_ax, p_ax = set_up_column_plot()
        header_ax = h_ax['main']
        plot_ax = p_ax['main']

    if block_name is None:
        block_name = def_lb_name

    tb = well.block[block_name]  # this log block
    depth = tb.logs['depth'].values

    if mask is None:
        mask = np.array(np.ones(len(depth)), dtype=bool)  # All True values -> all data is included

    if z_min is None:
        z_min = np.min(depth[mask])
    if z_max is None:
        z_max = np.max(depth[mask])

    log_types = [x for x in try_these_log_types if (len(well.get_logs_of_type(x)) > 0)]
    # TODO
    # Now we take the first log of each log type, generalize this so that it by default takes the first, but
    # can plot all or one specific
    log_names = {ltype: well.get_logs_of_type(ltype)[0].name for ltype in log_types}
    limits = [[templates[x]['min'], templates[x]['max']] for x in log_types]
    styles = [{'lw': templates[x]['line width'],
               'color': templates[x]['line color'],
               'ls': templates[x]['line style']} for x in log_types]
    legends = ['{} [{}]'.format(log_names[x], templates[x]['unit']) for x in log_types]

    if fill_betweens is not None:
        if not isinstance(fill_betweens, list):
            raise IOError('fill_betweens must be a list')
        _fill_betweens = []
        for fill in fill_betweens:
            skip = False
            indexes = []
            for _logtype in fill[:2]:
                if _logtype is None:
                    indexes.append(None)
                elif _logtype.replace('.', '', 1).isdigit():
                    indexes.append(_logtype)
                else:
                    if _logtype not in log_types:
                        info_txt = 'Log type {} not found among listed log types'.format(_logtype)
                        print('INFO: {}'.format(info_txt))
                        logger.info(info_txt)
                        _fill_betweens = None
                        skip = True
                    indexes.append(log_types.index(_logtype))
            if skip:
                continue
            # _fill_betweens.append((log_types.index(fill[0]), log_types.index(fill[1]), fill[2]))
            _fill_betweens.append((*indexes, fill[2]))
    else:
        _fill_betweens = None

    if len(log_types) == 0:
        header_plot(header_ax, None, None, None, title='Data is lacking')
        axis_plot(plot_ax, None, None, None, None, ylim=[z_min, z_max])
    else:
        xlims = axis_plot(plot_ax, depth[mask],
                          [tb.logs[log_names[xx]].values[mask] for xx in log_types],
                          limits, styles, yticks=False, fill_betweens=_fill_betweens,
                          ylim=[z_min, z_max])
        header_plot(header_ax, xlims, legends, styles)


def true_plot(ax, y, data, true_color='b', yticks=True, **kwargs):
    """
    Plot data in one subplot
    :param ax:
        matplotlib axes object
    :param y:
        numpy ndarray
        The depth data of length N
    :param data:
        Boolean array of length N
            or
        Array which is either 1 or 0
    :param true_color:
        str
        color string for the coloring the true values
    :param yticks:
        bool
        if False the yticklabels are not shown
    :param nxt:
        int
        Number of gridlines in x direction
    :param kwargs:
    """
    ylim = kwargs.pop('ylim', None)
    if data is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        return

    if isinstance(data, np.ndarray):
        if data.dtype is np.dtype('bool'):
            # convert true values to one
            x = np.zeros(len(data))
            x[data] = 1
        else:
            x = data
    else:
        raise IOError('Data must be an array')

    ax.fill_between(x, y, color=true_color, alpha=0.5)
    ax.set_xlim([0.1, 1])
    ax.get_xaxis().set_ticks([])
    if not yticks:
        ax.get_yaxis().set_ticklabels([])
    if ylim is not None:
        ax.set_ylim(ylim[::-1])
    else:
        ax.set_ylim(ax.get_ylim()[::-1])


def axis_plot_with_color_gradient(ax, y, data, limit, style, yticks=True, nxt=4, cmap=None, vmin=None, vmax=None,
                                  horizontal_gradient=True, **kwargs):
    """
    Plot one data set in one subplot.
    The data can be colored by a gradient defined by the cmap
    Recipe is taken from https://stackoverflow.com/questions/19132402/set-a-colormap-under-a-graph

    :param ax:
        matplotlib axes object
    :param y:
        numpy ndarray
        The depth data of length N
    :param data:
        numpy ndarray
        data of length N, which should be plotted
    :param limit:
        list
        list with min, max value of the data
        E.G. [0, 150]
    :param style:
        dict
        dictionary that defines the plotting styles of the data
        E.G. {'lw':1, 'color':'k', 'ls':'-'}
    :param yticks:
        bool
        if False the yticklabels are not shown
    :param nxt:
        int
        Number of gridlines in x direction
    :param cmap:
        matplotlib colormap object
        E.G. matplotlib.pyplot.cm.autumn
    :param vmin, vmax:
        floats
        values that determines the lower and upper value the color map should cover
    :param horizontal_gradient
        bool
        If True, the color gradient is horizontal
        else it is vertical
    :param kwargs:
        :param ylim:
        list of min max value of the y axis
    :return:
        list
        xlim, the limits (min, max) of the x axis
    """
    if cmap is None:
        from blixt_geo_py.utils.definitions import gr_cmap
        cmap = gr_cmap()

    if style is None:
        style = {'lw': 0.5, 'color': 'k', 'ls': '-'}

    ylim = kwargs.pop('ylim', None)
    n = kwargs.pop('n', 100)  # length of one side of the 'dummy' image
    if data is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        return

    # We need to make sure that the first and last valid value (not NaN) of the data are forced to zero. Else the
    # ax.fill() function will not deliver the necessary result
    nanmask = np.ma.masked_invalid(data).mask
    valid_data = data[~nanmask]
    valid_data[0] = 0; valid_data[-1] = 0

    # plot only the outline of the polygon, and capture the result
    poly, = ax.fill(valid_data, y[~nanmask], facecolor='none')
    # poly, = ax.fill(data, y, 'r')
    if ylim is not None:
        ax.set_ylim(*ylim)

    # get the extent of the axes
    # xmin, xmax = ax.get_xlim()
    xmin, xmax = limit[0], limit[1]
    ymin, ymax = ax.get_ylim()

    if vmin is None:
        vmin = xmin
    if vmax is None:
        vmax = xmax

    # create a dummy image
    if horizontal_gradient:
        img_data = np.arange(xmin, xmax, (xmax - xmin) / n)
        img_data = img_data.reshape(img_data.size, 1)
        extent = [xmin, xmax, ymin, ymax]
    else:
        img_data = np.tile(valid_data[::-10], (len(valid_data[::-10]), 1))
        extent = [xmin, xmax, np.min(y[~nanmask]), np.max(y[~nanmask])]

    img_data = np.transpose(img_data)

    im = ax.imshow(img_data, aspect='auto', origin='upper', cmap=cmap, extent=extent,
                   vmin=vmin, vmax=vmax)
    im.set_clip_path(poly)

    ax.plot(valid_data, y[~nanmask], **style)
    ax.set_xlim(*limit)
    if ylim is not None:
        ax.set_ylim(ylim[::-1])
    else:
        ax.set_ylim(ax.get_ylim()[::-1])
    if not yticks:
        ax.get_yaxis().set_ticklabels([])

    return [xmin, xmax]


def axis_plot(ax, y, data, limits, styles, yticks=True, nxt=4, fill_betweens=None, **kwargs):
    """
    Plot data in one subplot
    :param ax:
        matplotlib axes object
    :param y:
        numpy ndarray
        The depth data of length N
    :param data:
        list
        list of ndarrays, each of length N, which should be plotted in the same subplot
    :param limits:
        list
        list of lists, each with min, max value of respective curve, e.g.
        [[0, 150], [6, 16], ...]
    :param styles:
        list
        list of dictionaries that defines the plotting styles of the data
        E.G. [{'lw':1, 'color':'k', 'ls':'-'}, {'lw':2, 'color':'r', 'ls':'-'}, ... ]
    :param yticks:
        bool
        if False the yticklabels are not shown
    :param nxt:
        int
        Number of gridlines in x direction
    :param fill_betweens:
        list
        list of (data1 index, data2 index, color) triplets which determines the fill_between color when data1 is plotted
         to the right of data2 (data1 is not necessarily larger than data2, but plots to the right of data2 given the
         limits
         E.G. [(0, 1, 'brown'), (1, 0, 'yellow')]

         It can also specified with a None, E.G. [(0, None, 'brown'), ...], which counts a the constant value
         zero, or with strings, E.G. [(0, '40.', 'brown'), ...], Then the fill is between the constant value
         0 in the first case, and 40 in the second, and the curve data[0]

    :param kwargs:
        :param ylim:
        list of min max value of the y axis
    :return:
        list
        xlim, list of list, each with the limits (min, max) of the x axis
    """
    ylim = kwargs.pop('ylim', None)
    if data is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        return

    if not (len(data) == len(limits) == len(styles)):
        raise IOError('Must be same number of items in data, limits and styles')

    # store the x axis limits that has been used in each axis
    xlims = []

    # set up multiple twin axes to allow for different scaling of each plot
    axes = []
    for i in range(len(data)):
        if i == 0:
            axes.append(ax)
        else:
            axes.append(axes[-1].twiny())
    # Adjust the positions according to the original axes
    for i, ax in enumerate(axes):
        if i == 0:
            pos = ax.get_position()
        else:
            ax.set_position(pos)

    # start plotting
    for i in range(len(data)):
        axes[i].plot(data[i], y, **styles[i])

    if fill_betweens is not None:
        if not isinstance(fill_betweens, list):
            raise IOError('fill_betweens must be a list')
        for fill in fill_betweens:
            # try to cover the case when filling between a curve and a constant
            if fill[0] is None:
                data_0 = 0.0
                min_limit_0 = limits[fill[1]][0]  # when this is None, use the limits of the other data
                delta_limit_0 = limits[fill[1]][1] - limits[fill[1]][0]
            elif isinstance(fill[0], str):
                data_0 = float(fill[0])
                min_limit_0 = limits[fill[1]][0]
                delta_limit_0 = limits[fill[1]][1] - limits[fill[1]][0]
            elif isinstance(fill[0], int):
                data_0 = data[fill[0]]
                min_limit_0 = limits[fill[0]][0]
                delta_limit_0 = limits[fill[0]][1] - limits[fill[0]][0]
            else:
                raise IOError('Error in fill_betweens: ', fill[0])
            if fill[1] is None:
                data_1 = 0.0
                min_limit_1 = limits[fill[0]][0]
                delta_limit_1 = limits[fill[0]][1] - limits[fill[0]][0]
            elif isinstance(fill[1], str):
                data_1 = float(fill[1])
                min_limit_1 = limits[fill[0]][0]
                delta_limit_1 = limits[fill[0]][1] - limits[fill[0]][0]
            elif isinstance(fill[1], int):
                data_1 = data[fill[1]]
                min_limit_1 = limits[fill[1]][0]
                delta_limit_1 = limits[fill[1]][1] - limits[fill[1]][0]
            else:
                raise IOError('Error in fill_betweens: ', fill[1])

            # sd is the scaled version of the data that matches data[0]
            sd0 = limits[0][0] + (limits[0][1] - limits[0][0]) * \
                  (data_0 - min_limit_0) / delta_limit_0
            sd1 = limits[0][0] + (limits[0][1] - limits[0][0]) * \
                  (data_1 - min_limit_1) / delta_limit_1
            axes[0].fill_betweenx(y, sd0, sd1, sd0 > sd1, color=fill[2])

    # set up the x range differently for each plot
    for i in range(len(data)):
        # axes[i].set_xlim(*limits[i])
        set_lim(axes[i], limits[i], 'x')
        # print(limits[i])
        xlims.append(axes[i].get_xlim())
        # Change major ticks to set up the grid as desired
        if nxt > 0:
            xlim = axes[i].get_xlim()
            x_int = np.abs(xlim[1] - xlim[0]) / (nxt + 1)
            axes[i].xaxis.set_major_locator(MultipleLocator(x_int))
            axes[i].get_xaxis().set_ticklabels([])
        else:
            axes[i].get_xaxis().set_ticks([])
        if i == 0:
            if ylim is not None:
                axes[i].set_ylim(ylim[::-1])
            else:
                axes[i].set_ylim(ax.get_ylim()[::-1])
            if not yticks:
                axes[i].get_yaxis().set_ticklabels([])
        else:
            axes[i].tick_params(axis='x', length=0.)

    ax.grid(which='major', alpha=0.5)

    return xlims


def deltalogr_plot(ax, y, data, limits, styles, yticks=True, nxt=4, **kwargs):
    """
    Plot DeltaLogR in one subplot

    From Neal Morgan
    Plot AC [us/ft] on 200-0 scale
    Plot RDEP [Ohm m] with four decades of log scale (0.2 – 2000, 0.1-1000, 0.01-100, 0.001-10)

    Change the RDEP scale until logs overlay in a water filled zone which has no organic matter (source rock or coal)
    DLOGR is related to the Total Organic Carbon (TOC) and Level of Maturity  of the source rock (LOM)

    DLOGR = log10(RDEP/RDEPbaseline) + 0.02(AC-ACbaseline)

    TOC = DLOGR*10(2.297-0.1688*LOM)

    Good indicator of source rock and conventional hydrocarbon filled reservoirs

    The level of maturity LOM can be estimated (guessed) from the AC-RDEP separation
    LOM =7 onset of maturity for oil-prone kerogen
    LOM=12 onset of overmaturity for oil-rone kerogen

    :param ax:
        matplotlib axes object
    :param y:
        numpy ndarray
        The depth data of length N
    :param data:
        list
        list of two ndarrays, each of length N.
        First contains the Sonic, AC, in us/ft, the second the deep resistivity, RDEP, in Ohm m.

    :param limits:
        list
        list of lists, each with min, max value of respective curve, e.g.
        [[200, 0], [0.2, 2000]]
    :param styles:
        list
        list of dictionaries that defines the plotting styles of the data
        E.G. [{'lw':1, 'color':'k', 'ls':'-'}, {'lw':2, 'color':'r', 'ls':'-'}, ... ]
    :param yticks:
        bool
        if False the yticklabels are not shown
    :param nxt:
        int
        Number of gridlines in x direction
    :param kwargs:
        :param ylim:
        list of min max value of the y axis
    :return:
        list
        xlim, list of list, each with the limits (min, max) of the x axis
    """
    ylim = kwargs.pop('ylim', None)
    if data is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        return

    if not (len(data) == len(limits) == len(styles)):
        raise IOError('Must be same number of items in data, limits and styles')

    # store the x axis limits that has been used in each axis
    xlims = []

    # start plotting
    # Start with the sonic log (plotting on a reverse scale!)
    ax.plot(limits[0][0] - data[0], y, **styles[0])

    # Find linear function f(t) = a * t + b that will adjust the logarithmic resistivity values to the limits of the
    # sonic
    a = (limits[0][0] - limits[0][1]) / (np.log10(limits[1][1]) - np.log10(limits[1][0]))
    b = limits[0][1] - a * np.log10(limits[1][0])

    # Then plot the logarithm of the resistivity times the adjustment function f(t)
    ax.plot(np.log10(data[1]) * a + b, y, **styles[1])

    ax.fill_betweenx(
        y,
        np.log10(data[1]) * a + b,
        limits[0][0] - data[0], np.log10(data[1]) * a + b > (limits[0][0] - data[0]),
        color='r'
    )
    # We are not using twin axes in this plot because we want to use the fillbetween functionality
    # So instead of changing the axes limits individually, we need to adjust the resistivity values so
    # that its logarithm fits within the scale of the sonic (which is reversed!)
    set_lim(ax, limits[0][::-1])  # counteract the reverse scale
    xlims.append(limits[0])
    xlims.append(limits[1])

    if ylim is not None:
        ax.set_ylim(ylim[::-1])

    ax.get_xaxis().set_ticklabels([])
    if not yticks:
        ax.get_yaxis().set_ticklabels([])
        ax.tick_params(axis='y', length=0)
    ax.grid(which='major', alpha=0.5)

    return xlims


def axis_log_plot(ax, y, data, limits, styles, yticks=True,  **kwargs):
    """
    Plot data in one subplot
    Similar to axis_plot, but uses the same (logarithmic) x axis for all data
    
    The log axis can only handle one x range, so only the first range list in limits is used
    :param ax:
        matplotlib axes object
    :param y:
        numpy ndarray
        The depth data of length N
    :param data:
        list
        list of ndarrays, each of length N, which should be plotted in the same subplot
    :param limits:
        list
        min, max value of axis
        E.G. [0.2, 200]
    :param styles:
        list
        list of dictionaries that defines the plotting styles of the data
        E.G. [{'lw':1, 'color':'k', 'ls':'-'}, {'lw':2, 'color':'r', 'ls':'-'}, ... ]
    :param yticks:
        bool
        if False the yticklabels are not shown
    :param nxt:
        int
        Number of gridlines in x direction
    :param kwargs:
    :return:
        list
        xlims, list of list, each with the limits (min, max) of the x axis
    """
    if not (len(data) == len(styles)):
        raise IOError('Must be same number of items in data and styles')

    ylim = kwargs.pop('ylim', None)

    # store the x axis limits that has been used in each axis
    xlims = []

    # start plotting
    for i in range(len(data)):
        ax.plot(data[i], y, **styles[i])

    ax.set_xscale('log')
    #ax.set_xlim(*limits)
    set_lim(ax, limits[0], 'x')
    xlims.append(ax.get_xlim())
    ax.get_xaxis().set_ticklabels([])
    ax.tick_params(axis='x', which='both', length=0)

    if ylim is not None:
        ax.set_ylim(ylim[::-1])
    else:
        ax.set_ylim(ax.get_ylim()[::-1])
    if not yticks:
        ax.get_yaxis().set_ticklabels([])
        ax.tick_params(axis='y', length=0)

    ax.grid(which='major', alpha=0.5)
    ax.grid(which='minor', alpha=0.2)

    return xlims


def annotate_plot(ax, y, pad=-30, intervals=None, interval_names=None, interval_colors='cyclic', **kwargs):
    """
    Creates a, preferably thin in x direction, empty plot which annotates the y axis.
    Typically to show MD or TWT values
    Args:
        ax:
        y:
        pad:
        intervals:
            list of lists with top and base of N intervals, e.g.
            [[interval1_top, interval1_base], [interval2_top, interval2_base], ...]
        interval_names:
            list of N names to annotate the intervals
        interval_colors:
            list of N colors to color each interval
            if equal to string 'cyclic', two hardcoded colors are used to cyclically color each interval
        **kwargs:

    Returns:

    """
    # TODO
    # Remove the hardcoded cyclic coloring of intervals when needed
    interval_colors = 'cyclic'

    ylim = kwargs.pop('ylim', None)
    n_int = None
    if intervals is not None:
        n_int = len(intervals)
        if interval_names is not None:
            if len(interval_names) != n_int:
                raise IOError('Number of intervals must equal the number of interval names')
            if (interval_colors is not None) and (interval_colors != 'cyclic') and (len(interval_colors) != n_int):
                raise IOError('Number of intervals must equal the number of interval colors')

    if y is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        return

    # the y data can be masked, making the intervals look patchy.
    # Try fix this by using a "stiched" version of y
    this_y = np.linspace(np.nanmin(y), np.nanmax(y), 1000)

    ax.plot(np.ones(len(this_y)), this_y, lw=0)
    # draw intervals
    if (intervals is not None) and (interval_colors is not None) and (interval_colors == 'cyclic'):
        interval_colors = ['#E3F917', '#17becf'] * int(np.ceil(n_int / 2.))
    if intervals is not None:
        for i, _this_interval in enumerate(intervals):
            ax.axhline(y=_this_interval[0], color='k', lw=0.5)
            ax.axhline(y=_this_interval[1], color='k', lw=0.5)
            aboves = this_y > _this_interval[0]
            belows = this_y < _this_interval[1]
            selection = aboves & belows
            if interval_colors is not None:
                ax.fill_betweenx(this_y, np.ones(len(this_y)), where=selection, color=interval_colors[i])
        if interval_names is not None:
            for i, _this_name in enumerate(interval_names):
                _y = 0.5 * sum(intervals[i])
                if ylim is not None:  # skip printing interval names outside y limit
                    if (_y < ylim[0]) or (_y > ylim[1]):
                        continue
                ax.text((0.3 + np.mod(i, 2) * 0.4) * sum(ax.get_xlim()), _y, _this_name,
                        weight='bold', rotation='vertical', va='center')
    if ylim is not None:
        ax.set_ylim(ylim[::-1])
    else:
        ax.set_ylim(ax.get_ylim()[::-1])
    ax.get_xaxis().set_ticks([])
    ax.tick_params(axis='y', direction='in', length=5., labelsize='smaller', right=True)
    yticks = [*ax.yaxis.get_major_ticks()]
    for tick in yticks:
        tick.set_pad(pad)


def header_plot(ax, limits, legends, styles, title=None, **text_keywords):
    """
    Tries to create a "header" to a plot, similar to what is used in RokDoc and many CPI plots
    :param ax:
        matplotlib axes object
    :param limits:
        list
        list of lists, each with min, max value of respective curve, e.g.
        [[0, 150], [6, 16], ...]
        Should not be more than 4 items in this list
    :param legends:
        list
        list of strings, that should annotate the respective limits
    :param styles:
        list
        list of dicts which describes the line styles
        E.G. [{'lw':1, 'color':'k', 'ls':'-'}, {'lw':2, 'color':'r', 'ls':'-'}, ... ]
    :return:
    """
    ha = text_keywords.pop('ha', 'center')
    rotation = text_keywords.pop('rotation', 0)
    if limits is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        if title is not None:
            ax.text(0.5, 0.1, title, ha=ha, rotation=rotation)
        return

    if not (len(limits) == len(legends) == len(styles)):
        raise IOError('Must be same number of items in limits ({}), legends ({}) and styles ({})'.format(
            len(limits), len(legends), len(styles)
        ))

    # Sub divide plot in this number of horizontal parts
    n = 8
    for i in range(len(limits)):
        ax.plot([1, 1.333, 1.666, 2],  [n-1-2*i]*4, **styles[i])
        if abs(limits[i][0]) > 100:
            ax.text(1 - 0.03, n - 1 - 2 * i, '{:.0f}'.format(limits[i][0]), ha='right', va='center', fontsize='smaller')
            ax.text(2 + 0.03, n - 1 - 2 * i, '{:.0f}'.format(limits[i][1]), ha='left', va='center', fontsize='smaller')
        elif abs(limits[i][0]) > 10:
            ax.text(1 - 0.03, n - 1 - 2 * i, '{:.1f}'.format(limits[i][0]), ha='right', va='center', fontsize='smaller')
            ax.text(2 + 0.03, n - 1 - 2 * i, '{:.1f}'.format(limits[i][1]), ha='left', va='center', fontsize='smaller')
        else:
            ax.text(1-0.03, n-1-2*i, '{:.2f}'.format(limits[i][0]), ha='right', va='center', fontsize='smaller')
            ax.text(2+0.03, n-1-2*i, '{:.2f}'.format(limits[i][1]), ha='left', va='center', fontsize='smaller')
        ax.text(1.5, n-1-2*i+0.1, legends[i], ha='center', va='bottom', fontsize='smaller')

    ax.set_xlim(0.8, 2.3)
    ax.get_xaxis().set_ticks([])
    ax.set_ylim(0.5, 8)
    ax.get_yaxis().set_ticks([])
    if title is not None:
        ax.text(1.5, 0.6, title, ha='center')


def wiggle_plot(ax, y, wiggle, zero_at=0., scaling=1., fill_pos_style='pos-blue',
                fill_neg_style='neg-red', color_by_gradient=None, zero_style=None, yticks=True, **kwargs):
    """
    Draws a (seismic) wiggle plot centered at 'zero_at'
    :param ax:
        matplotlib Axis object
    :param y:
        numpy ndarray
        Depth variable
    :param wiggle:
        numpy ndarray
        seismic trace
    :param zero_at:
        float
        x value at which the wiggle should be centered
    :param scaling:
        float
        scale the data
    :param fill:
        str
        'neg': Fills the negative side of the wiggle
        'pos': Fills the positive side of the wiggle
        None : No fill
    :param color_by_gradient:
        numpy.array
        If this is set, the value of the gradient is used to determine the fill_between color.
        This way we can see the AVO class directly from the sign of the wiggle, and color of the fill, without
        having to plot several wiggles.
    :param zero_style:
        dict
        style keywords of the line marking zero
    :param kwargs:

    :return:
    """
    ylim = kwargs.pop('ylim', None)

    if y is None:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])
        return

    #print(len(y), len(wiggle))
    lw = kwargs.pop('lw', 0.5)
    c = kwargs.pop('c', 'k')

    if fill_pos_style == 'default':
        fill_pos_style = {'color': 'r', 'alpha': 0.2, 'lw': 0.}
    elif fill_pos_style == 'pos-blue':
        fill_pos_style = {'color': 'b', 'alpha': 0.2, 'lw': 0.}
    if fill_neg_style == 'default':
        fill_neg_style = {'color': 'b', 'alpha': 0.2, 'lw': 0.}
    elif fill_neg_style == 'neg-red':
        fill_neg_style = {'color': 'r', 'alpha': 0.2, 'lw': 0.}
    if zero_style is None:
        zero_style = {'lw': 0.5, 'color': 'k', 'alpha': 0.2}

    # shift and scale the data so that it is centered at 'zero_at'
    wig = zero_at + wiggle*scaling
    #print('Wiggle plot lengths: {}, {}'.format(len(wig), len(y)))
    ax.plot(wig, y, lw=lw, color=c, **kwargs)

    # Try with fill colors depending on sign of the gradient
    pos_amp_pos_gradient = False
    pos_amp_neg_gradient = False
    neg_amp_pos_gradient = False
    neg_amp_neg_gradient = False

    if color_by_gradient is not None and len(color_by_gradient) == len(wiggle):
        fill_pos_style = None
        fill_neg_style = None

        pos_amp_pos_gradient = np.array(np.zeros(len(wiggle)), dtype=bool)
        pos_amp_neg_gradient = np.array(np.zeros(len(wiggle)), dtype=bool)
        neg_amp_pos_gradient = np.array(np.zeros(len(wiggle)), dtype=bool)
        neg_amp_neg_gradient = np.array(np.zeros(len(wiggle)), dtype=bool)

        zero_crossings = np.where(np.diff(np.sign(wiggle) >= 0))[0]
        last_index = 0
        for index in zero_crossings:
            this_part = wiggle[last_index:index]
            if np.nanmean(this_part) > 0:  # positive amplitude
                if np.nanmean(color_by_gradient[last_index:index]) > 0:  # positive gradient
                    pos_amp_pos_gradient[last_index:index] = True
                else:  # negative gradient
                    pos_amp_neg_gradient[last_index:index] = True
            else:  # negative amplitude
                if np.nanmean(color_by_gradient[last_index:index]) > 0:
                    neg_amp_pos_gradient[last_index:index] = True
                else:  # negative gradient
                    neg_amp_neg_gradient[last_index:index] = True
            last_index = index

        # ax.plot(wig[zero_crossings], zero_crossings, 'o')

        ax.fill_betweenx(y, wig, zero_at, pos_amp_pos_gradient, **{'color': 'b', 'alpha': 1.0, 'lw': 0.})
        ax.fill_betweenx(y, zero_at, wig, neg_amp_pos_gradient, **{'color': 'b', 'alpha': 1.0, 'lw': 0.})
        ax.fill_betweenx(y, wig, zero_at, pos_amp_neg_gradient, **{'color': 'r', 'alpha': 1.0, 'lw': 0.})
        ax.fill_betweenx(y, zero_at, wig, neg_amp_neg_gradient, **{'color': 'r', 'alpha': 1.0, 'lw': 0.})

    if fill_pos_style is not None:
        ax.fill_betweenx(y, wig, zero_at, wig > zero_at, **fill_pos_style)
        #pass
    if fill_neg_style is not None:
        ax.fill_betweenx(y, zero_at, wig, wig < zero_at, **fill_neg_style)
        #pass

    ax.axvline(zero_at, **zero_style)

    if ylim is not None:
        ax.set_ylim(ylim[::-1])
    else:
        ax.set_ylim(ax.get_ylim()[::-1])
    if not yticks:
        ax.get_yaxis().set_ticklabels([])
        ax.tick_params(axis='y', length=0)


def ava_curve_plot(ax, incident_angles, ava_curves, styles=None ):
    """
    Plots a set of amplitude versus angle plots in one axes object
    :param ax:
        Axes object
    :param    incident_angles:
        list
        List of incident angles in degrees
    :param ava_curves:
        np.ndarray
        size len(incident_angles), len(extract_at)
        Array with AVA (amplitude versus angle) curves, one for each "extract_at" float.
    :param styles:
        list
        list of dicts which describes the line styles
        E.G. [{'lw':1, 'color':'k', 'ls':'-'}, {'lw':2, 'color':'r', 'ls':'-'}, ... ]
    :return:
    """
    # Get axis "physical" size
    fig = ax.get_figure()
    bbox = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    bbox_aspect_ratio = bbox.width / bbox.height
    print(bbox_aspect_ratio)
    if bbox_aspect_ratio < 0.5:
        this_ax = ax.inset_axes([0.1, 0.5, 0.88, 0.3])
    else:
        this_ax = ax

    for i in range(ava_curves.shape[1]):
        this_ax.plot(incident_angles, ava_curves[:, i], **styles[i])

    this_ax.axhline(0, 0, 1, c='k', ls='--')
    this_ax.set_xlabel('Incident angle')


def chi_rotation_plot(eeis, y, chi_angles, eei_limits, line_colors=None, legends=None, reference_log=None,
                      reference_template=None):
    """
    Plot the EEI for different elastic logs (typically brine, gas, oil) for different chi angles so that it is easy
    to see at which chi angles we have the largest sensitivity to fluids and lithology
    Args:
        eeis:
            numpy.ndarray of size (K, M, N)
            Array containing the extended elastic impedance for M different chi angles, for the N different set of logs
        y
            numpy.ndarray of size K
            The common y axis for all eeis
        chi_angles:
            list, length M
            List of floats specifying the Chi angles (deg) used
        eei_limits:
            list, of length M
            Each item of eei_limits is a tuple or list of length N
            Each of these sub-items is a list with min and max values for the EEI at that specific
            chi angle and for each set of elastic logs
        line_colors:
            list, length N
            M item long list of strings of color names used to separate the different eei's (common for all chi angles)
            Default is ['b', 'g', 'r']
        legends
            list
            List of the names of the different eei's (common for all chi angles)
            Default is ['Brine', 'Oil', 'Gas']
        reference_log:
            numpy.ndarray of length K
            Reference well log that is plotted on a separate axes (when provided) which make it easier for the user
            to orient themself in the lithostratigraphy. Preferably a gamma ray log
        reference_template:
            dict
            Dictionary that contains the settings for plotting the reference log.
            Must contain the following key words:
                'line width' for the line width
                'line color' for the line color
                'line style' for the line style
                'min' minimum plot range value
                'max' maximum plot range value
                'unit' Units used
                'full_name' Name of the reference log

    Returns:
        fig:
            Matplotlib.pyplot.Figure object
        axes:
            list of Matplotlib.pyplot.Axes objects, axes with eei data, one for each chi angles
        header_axes
            list of Matplotlib.pyplot.Axes objects, axes with header, one for each chi angles

    """
    k, m, n = eeis.shape
    if len(y) != k:
        raise IOError('Length of y coordinate ({}) is different from length of eei ({})'.format(
            len(y), k
        ))
    if line_colors is None:
        line_colors = ['b', 'g', 'r']
    if legends is None:
        legends = ['Brine', 'Oil', 'Gas']
    if (len(line_colors) != n) or (len(legends) != n):
        raise IOError('Number of colors ({}) or legends ({}) does not match number of logs ({})'.format(
            len(line_colors), len(legends), n
        ))

    if reference_log is not None:
        if reference_template is None:
            raise IOError('The reference log is lacking its template')

    styles = [{'lw': 1.,
               'color': line_colors[i],
               'ls': '-'} for i in range(len(line_colors))]

    # set up plot window
    fig = plt.figure(figsize=(20, 10))
    n_cols = len(chi_angles)
    if reference_log is not None:
        n_cols += 1  # add an extra column for the reference log
    n_rows = 2
    height_ratios = [1, 5]
    spec = fig.add_gridspec(nrows=n_rows, ncols=n_cols,
                            height_ratios=height_ratios,
                            hspace=0., wspace=0.,
                            left=0.05, bottom=0.03, right=0.98, top=0.96)
    header_axes = []
    axes = []
    for i in range(n_cols):
        header_axes.append(fig.add_subplot(spec[0, i]))
        axes.append(fig.add_subplot(spec[1, i]))

    # Start plotting data
    if reference_log is not None:
        this_style = [{'lw': reference_template['line width'],
                       'color': reference_template['line color'],
                       'ls': reference_template['line style']}]
        xlims = axis_plot(axes[0], y, [reference_log], [[reference_template['min'], reference_template['max']]],
                          this_style, ylim=[y[0], y[-1]])
        header_plot(header_axes[0], xlims, ['{} [{}]'.format(reference_template['full_name'],
                                                             reference_template['unit'])], this_style)
    for i, chi in enumerate(chi_angles):
        if reference_log is not None:
            axes_i = i + 1
        else:
            axes_i = i
        xlims = axis_plot(axes[axes_i], y, [eeis[:, i, j] for j in range(n)],
                          eei_limits[i], styles, ylim=[y[0], y[-1]], yticks=axes_i==0)

        header_plot(header_axes[axes_i], xlims, legends, styles, title=r'Chi {:.0f}$^\circ$'.format(chi))

    return fig, axes, header_axes


def set_lim(ax, these_limits, axis=None):
    """
    Convinience function to set the x axis limits. Interprets None as autoscale
    :param ax:
        matplotlib.axes
    :param these_limits:
        list
        list of  min, max value.
        If any is None, axis is autoscaled
    :param axis
        str
        'x' or 'y'
    :return:
    """
    if axis is None:
        return
    
    if len(these_limits) != 2:
        print("WARNING, 'these_limits' must have length 2. Now it has length {}".format(len(these_limits)))
        these_limits = [None, None]

    # Remove unintentional text strings that might exist in the min/max of the templates
    for _i in range(2):
        if isinstance(these_limits[_i], str):
            these_limits[_i] = None

    if None in these_limits:
        print('limits', these_limits)
        # first autoscale
        ax.autoscale(True, axis=axis)
        if axis == 'x':
            _lims = ax.get_xlim()
            ax.set_xlim(
                left=these_limits[0] if these_limits[0] is not None else _lims[0],
                right=these_limits[1] if these_limits[1] is not None else _lims[1]
            )
        else:
            _lims = ax.get_ylim()
            ax.set_ylim(
                these_limits[0] if these_limits[0] is not None else _lims[0],
                these_limits[1] if these_limits[1] is not None else _lims[1]
            )
    else:
        if axis == 'x':
            ax.set_xlim(*these_limits)
        else:
            ax.set_ylim(*these_limits)


def plot_ampspec(ax, freq, amp, f_peak, name=None):
    '''
    plot_ampspec (C) aadm 2016-2018
    Plots amplitude spectrum calculated with mpfullspec (aageofisica.py).

    INPUT
    ax, axis object. If None, creates a new figure
    freq: frequency
    amp: amplitude
    f_peak: average peak frequency
    '''
    db = 20 * np.log10(amp)
    db = db - np.amax(db)
    if ax is None:
        f, ax = plt.subplots(nrows=1, ncols=2, figsize=(12, 5), facecolor='w')
    ax[0].plot(freq, amp, '-k', lw=2)
    ax[0].set_ylabel('Power')
    ax[1].plot(freq, db, '-k', lw=2)
    ax[1].set_ylabel('Power (dB)')
    for aa in ax:
        aa.set_xlabel('Frequency (Hz)')
        aa.set_xlim([0, np.amax(freq) / 1.5])
        aa.grid()
        aa.axvline(f_peak, color='r', ls='-')
        if name != None:
            aa.set_title(name, fontsize=16)


def plot_ampspecs(ax, freq_amp_list, names=None):
    '''Plots overlay of multiple amplitude spectras.

    A variation of:
    plot_ampspec2 (C) aadm 2016-2018
    https://nbviewer.jupyter.org/github/aadm/geophysical_notes/blob/master/playing_with_seismic.ipynb
    which takes a list of multiple freqency-amplitude pairs (with an optional "average peak frequency")

    INPUT
        ax, axis object. If None, creates a new figure

        freq_amp_list: list of
        [frequency (np.ndarray), amplitude spectra (np.ndarray), optional average peak frequency (float)] lists

        names: list of strings, same length as freq_amp_list

    '''
    dbs = []  # list to hold dB values of the amplitude spectra
    for _item in freq_amp_list:
        _db = 20 * np.log10(_item[1])
        dbs.append(_db - np.amax(_db))

    one_axes = True
    if ax is None:
        fig, ax = plt.subplots(nrows=1, ncols=2, figsize=(12, 5), facecolor='w')
        one_axes = False

    labels = None
    if names is not None:
        if len(freq_amp_list) != len(names):
            raise ValueError('Both input lists must have same length')

        labels = []
        for i, _name in enumerate(names):
            _label = '{}'.format(_name)
            if len(freq_amp_list[i]) > 2:
                if (freq_amp_list[i][2] is not None):
                    _label += ' Fp={:.0f} Hz'.format(freq_amp_list[i][2])
            labels.append(_label)
    if labels is None:
        labels = [''] * len(freq_amp_list)

    saved_colors = []
    for i, _item in enumerate(freq_amp_list):
        tc = next_color()
        saved_colors.append(tc)
        if one_axes:
            ax.plot(_item[0], dbs[i], '-{}'.format(tc), lw=2, label=labels[i])
        else:
            ax[0].plot(_item[0], _item[1], '-{}'.format(tc), lw=2, label=labels[i])
            ax[0].fill_between(_item[0], 0, _item[1], lw=0, facecolor=tc, alpha=0.25)
            ax[1].plot(_item[0], dbs[i], '-{}'.format(tc), lw=2, label=labels[i])

    if one_axes:
        lower_limit = np.min(ax.get_ylim())
        ax.fill_between(_item[0], dbs[i], lower_limit, lw=0, facecolor=saved_colors[i], alpha=0.25)
        ax.set_xlabel('Frequency (Hz)')
        ax.grid()
        ax.set_ylabel('Power (dB)')
        ax.legend(fontsize='small')

    else:
        lower_limit = np.min(ax[1].get_ylim())
        for i, _item in enumerate(freq_amp_list):
            ax[1].fill_between(_item[0], dbs[i], lower_limit, lw=0, facecolor=saved_colors[i], alpha=0.25)
            for i, _item in enumerate(freq_amp_list):
                if len(freq_amp_list[i]) > 2:
                    if (freq_amp_list[i][2] is not None):
                        ax.axvline(freq_amp_list[i][2], color=saved_colors[i], ls='-')


        ax[0].set_ylabel('Power')
        ax[1].set_ylabel('Power (dB)')
        for aa in ax:
            aa.set_xlabel('Frequency (Hz)')
            # aa.set_xlim([0,np.amax(freq)/1.5])
            aa.grid()
            for i, _item in enumerate(freq_amp_list):
                 if len(freq_amp_list[i]) > 2:
                    if (freq_amp_list[i][2] is not None):
                        aa.axvline(freq_amp_list[i][2], color=saved_colors[i], ls='-')

            aa.legend(fontsize='small')


def confidence_ellipse(x, y, ax, n_std=3.0, facecolor='none', **kwargs):
    """
    Plotting a confidence ellipsis as based on the
    https://matplotlib.org/stable/gallery/statistics/confidence_ellipse.html
    example

    Args:
        x, y : array-like, shape (n, )
            Input data.

        ax: matplotlib.axes.Axes
            The axes object to draw the ellipse in

        n_std: float
            The number of standard deviations to determine the ellipse's radiuses
        **kwargs
            Forwarded to the ~matplotlib.patches.Ellipse

    Returns:
        matplotlib.patches.Ellipse
    """
    from matplotlib.patches import Ellipse
    from matplotlib.transforms import Affine2D

    if x.size != y.size:
        raise ValueError("x and y must be the same size")

    cov = np.cov(x, y)
    xy_corr_coef = cov[0, 1] / np.sqrt(cov[0, 0] * cov[1, 1])
    # Using a special case to obtain the eigenvalues of this
    # two-dimensional dataset.
    ell_radius_x = np.sqrt(1 + xy_corr_coef)
    ell_radius_y = np.sqrt(1 - xy_corr_coef)
    ellipse = Ellipse((0, 0), width=ell_radius_x * 2, height=ell_radius_y * 2,
                      facecolor=facecolor, **kwargs)

    x_std = np.sqrt(cov[0, 0])
    scale_x = x_std * n_std
    x_mean = np.mean(x)

    y_std = np.sqrt(cov[1, 1])
    scale_y = y_std * n_std
    y_mean = np.mean(y)

    transf = Affine2D() \
        .rotate_deg(45) \
        .scale(scale_x, scale_y) \
        .translate(x_mean, y_mean)

    ellipse.set_transform(transf + ax.transData)
    return ax.add_patch(ellipse)


def wavelet_plot(ax, time, wavelet, header=None, orientation='right', show_ticks=True):
    """

    :param ax:
    :param wavelet:
    :param time:
    :param header:
    :param orientation:
        str
        The orientation of the time axis
        'right', 'down'
    :return:
    """
    text_style = {'fontsize': 'x-small', 'bbox': {'facecolor': 'lightgray', 'alpha': 0.4}}
    info_txt = ''
    if header is not None:
        for key in list(header.keys()):
            if key in ['Original filename', 'Name']:
                continue
            info_txt += '{}: {}\n'.format(key, header[key])
        info_txt = info_txt[:-1]
    if ax is None:
        fig, ax = plt.subplots()

    x_pos, ha = None, None
    if orientation == 'down':
        ax.plot(wavelet, time)
        x_pos = 1
        ha = 'right'
        ax.set_ylim(ax.get_ylim()[::-1])
    elif orientation == 'right':
        ax.plot(time, wavelet)
        x_pos = 0
        ha = 'left'

    if header is not None:
        ax.set_title(header['Name'])
        ax.text(ax.get_xlim()[x_pos], ax.get_ylim()[1], info_txt,
                ha=ha, va='top', **text_style)

    if not show_ticks:
        ax.get_xaxis().set_ticks([])
        ax.get_yaxis().set_ticks([])

