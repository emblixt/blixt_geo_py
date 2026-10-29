import logging
from copy import deepcopy

import blixt_geo_py.rp.anisotropy as bra
import matplotlib.pyplot as plt
import numpy as np
from blixt_geo_py.plotting import crossplot as xp
from blixt_geo_py.utils.utils import print_info
from matplotlib.colors import to_hex
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D

from blixt_geo_py.core.core import CutoffRule, Cutoffs, LogTable
import blixt_geo_py.rp.rp_core as rp

logger = logging.getLogger(__name__)
opt1 = {'bbox': {'facecolor': '0.9', 'alpha': 0.5, 'edgecolor': 'none'}}
opt2 = {'ha': 'right', 'bbox': {'facecolor': '0.9', 'alpha': 0.5, 'edgecolor': 'none'}}


def _ref_val_of(ref_val: dict | None, well_name: str):
    """
    Returns the reference Vp, Vs and rho of the given well from ref_val, matching the well name regardless of upper or
    lower case
    """
    if ref_val is None:
        raise ValueError('Reference values for each well is needed for plot type I-G, Phi-%AI, Phi-I and Phi-G')
    for _name, _val in ref_val.items():
        if _name.lower() == well_name.lower():
            return _val
    raise ValueError('Reference values of Vp, Vs and rho are lacking for well {}'.format(well_name))


def _template_of(well, log_name: str, units) -> dict:
    """
    Returns the style of the given log as a template dictionary that crossplot.plot() understands
    """
    template = dict(well.get_log_curve(log_name).style.__dict__)
    template['full_name'] = template.get('full_name') or log_name
    template['units'] = '{:~P}'.format(units)
    return template


def plot_rp(wells, log_table, wis, wi_name, cutoffs=None, legend_items=None,
            plot_type=None, ref_val=None, ax=None, color_by=None, size_by=None, savefig=None,
            backus=False, **kwargs):

    """
    Plots some standard rock physics crossplots for the given wells

    :param wells:
        list or dict
        core.well.Well objects, e.g. wp.wells after
            wp = Project(...)
            wp.load_all_wells()
    :param log_table:
        LogTable or dict
        Log type: log name key: value pairs which decides which log, under each log type, to plot
        E.G.
            log_table = {
               'P velocity': 'vp',
               'S velocity': 'vs',
               'Density': 'rhob',
               'Porosity': 'phie',
               'Volume': 'vcl'}
        If 'P velocity' is not given, the velocities are calculated from the 'Sonic' and 'Shear sonic' logs
    :param wis:
        Intervals
        working intervals, e.g. from wp.load_all_wis()
    :param wi_name:
        str
        name of working interval to plot
    :param cutoffs:
        Cutoffs, str (e.g. "Volume<0.5[], Porosity>0.1[]"), dict (e.g. {'Volume': ['<', 0.5]}) or None
        Rules may refer to log types (e.g. 'Volume') or log names (e.g. 'vcl')
    :param legend_items:
        list
        list of Line2D objects that are used in the legends.
        if None, the well names will be used
    :param plot_type:
        str
        plot_type =
            'AI-VpVs': AI versus Vp/Vs plot
            'Phi-Vp': Porosity versus Vp plot
            'I-G': Intercept versus Gradient plot
            'Phi-%AI', 'Phi-I', 'Phi-G': Porosity versus relative AI, Intercept or Gradient
            'Vp-tvd', 'VpVs-tvd', 'AI-tvd', 'Rho-tvd': versus TVD
            'Vp-bd', 'VpVs-bd', 'AI-bd', 'Rho-bd': versus burial depth (TVD below the sea floor)
    :param ref_val:
        dict
        dictionary with well names as keys. Each value is a list of reference
        Vp [m/s], Vs [m/s], and rho [g/cm3] that are used
        when calculating the Intercept and gradient
    :param ax:
    :param color_by:
        str
        If None, data are colored according to each individual wells style, else set it to
        a log type in the log table, and it tries to color the points based on that data
    :param size_by:
        str
        If None, data are sized the same ("pointsize"), else, this log type determines the size
    :param savefig
        str
        full pathname of file to save the plot to
    :param backus:
        bool
        If true, Vp, Vs and Rho are Backus averaged before plotting
    :param **kwargs:
        keyword arguments passed on to crossplot.plot()
    :return:
        colorbar, legend
    """
    from blixt_geo_py.analysis.calc_stat_class import to_cutoffs

    #
    # some initial setups
    backus_length = 5.  # m
    if ref_val is not None:
        if not isinstance(ref_val, dict):
            raise ValueError('ref_val must be a dictionary with reference Vp, Vs and rho for each well')
    if isinstance(wells, dict):
        wells = list(wells.values())
    if not isinstance(log_table, LogTable):
        log_table = LogTable(dict(log_table))
    cutoffs = to_cutoffs(cutoffs)

    if plot_type is None:
        plot_type = 'AI-VpVs'
    elif plot_type == 'I-G' and ref_val is None:
        raise ValueError('Reference values for each well is needed for creating Intercept vs. Gradient plot')

    # The velocities are taken from the sonic logs when the velocity logs are not given
    use_sonic = 'P velocity' not in list(log_table.keys())
    needed_types = ['Density'] + (['Sonic', 'Shear sonic'] if use_sonic else ['P velocity', 'S velocity'])
    if plot_type.startswith('Phi-'):
        needed_types.append('Porosity')
    for _type in [color_by, size_by]:
        if isinstance(_type, str):
            needed_types.append(_type)
    missing_types = [_type for _type in needed_types if _type not in list(log_table.keys())]
    if len(missing_types) > 0:
        raise ValueError('The log table lacks the log types: {}'.format(', '.join(missing_types)))
    logs = [log_table[_type] for _type in needed_types]
    # Convert rules on log types (e.g. 'Volume') to rules on log names (e.g. 'vcl')
    rules = cutoffs.use_log_table(log_table).cutoffs

    #
    # set up plotting environment
    if ax is None:
        fig, ax = plt.subplots(figsize=(10, 10))
    else:
        fig = ax.get_figure()

    well_styles = []  # (well name, color, marker) of the plotted wells, used in the legend
    cbar = None
    for counter, _well in enumerate(wells):
        print_info('Plotting well {}'.format(_well.name), 'info', logger)
        # create a deep copy of the well so that the original is not altered
        well = deepcopy(_well)
        # Don't use Intervals.get_cutoff_rule(), which falls back to the whole well when the interval is missing
        interval = wis.get_interval(wi_name, well.name)
        if interval is None:
            warn_txt = 'Working interval {} does not exist in well {}'.format(wi_name, well.name)
            print_info(warn_txt, 'warning', logger)
            continue  # this working interval does not exist in current well
        # test if necessary logs are in the well
        missing = [_log for _log in logs if _log not in well.get_log_names]
        if len(missing) > 0:
            print_info('{} log(s) lacking in {}'.format(', '.join(missing), well.name), 'warning', logger)
            continue

        # The depth is needed for the interval, and the depth plots need the TVD, or the burial depth
        if 'md' not in well.get_log_names:
            well.create_md_log()
        depth_name = None
        if plot_type.endswith('-tvd'):
            _tvd_logs = [_l.name for _l in well.get_logs_of_type('TVD') if _l.name != 'tvd_ml']
            if len(_tvd_logs) == 0:
                print_info('TVD log lacking in {}'.format(well.name), 'warning', logger)
                continue
            depth_name = _tvd_logs[0]
        elif plot_type.endswith('-bd'):
            if 'tvd_ml' not in well.get_log_names:
                well.create_tvd_ml_log()
            if 'tvd_ml' not in well.get_log_names:
                continue  # create_tvd_ml_log() has warned about what is lacking
            depth_name = 'tvd_ml'

        # Build new Cutoffs for each well, so the interval rule is not added to the users cutoffs.
        # Keep all samples, and the mask, so that the Backus averaging is done on evenly sampled logs
        well_cutoffs = Cutoffs(cutoffs=deepcopy(rules) +
                               [CutoffRule('md', '><', [interval.top, interval.base])])
        data = well.dict(cutoffs=well_cutoffs, use_cutoffs=False)
        mask = data['mask']

        # Collect data for plot, start with Vp, Vs and Rho, in the units used by the rock physics functions
        rho = data[log_table['Density']].to('g/cm^3').magnitude
        rho_unit = 'g/cm3'
        vp_unit = vs_unit = 'm/s'
        if use_sonic:
            # The sonic logs are slowness, so the velocity is the reciprocal
            vp = (1. / data[log_table['Sonic']]).to(vp_unit).magnitude
            vs = (1. / data[log_table['Shear sonic']]).to(vs_unit).magnitude
        else:
            vp = data[log_table['P velocity']].to(vp_unit).magnitude
            vs = data[log_table['S velocity']].to(vs_unit).magnitude

        # Apply Backus average if requested
        if backus is True:
            dz = np.nanmedian(np.diff(data['md'].to('m').magnitude))
            vp, vs, rho = bra.backus(vp, vs, rho, backus_length, dz)[:3]

        y_depth = None
        if depth_name is not None:
            y_depth = data[depth_name].to('m').magnitude
            # E.g. the burial depth is NaN when the kelly bushing or water depth is lacking in the project table
            if not np.any(np.isfinite(y_depth[mask])):
                print_info('No valid {} values in {} of {}. Skipped'.format(depth_name, wi_name, well.name),
                           'warning', logger)
                continue
            ytempl = {'full_name': 'Burial depth' if depth_name == 'tvd_ml' else 'TVD', 'unit': 'm'}

        if plot_type == 'AI-VpVs':
            # Calculating Vp / Vs using vp and vs
            x_data = vp * rho
            x_unit = '{} {}'.format(vp_unit, rho_unit)
            y_data = vp / vs
            y_unit = '-'
            xtempl = {'full_name': 'AI', 'unit': x_unit}
            ytempl = {'full_name': 'Vp/Vs', 'unit': y_unit}

        elif plot_type in ['Vp-bd', 'Vp-tvd']:
            x_data = vp
            xtempl = {'full_name': log_table['P velocity'] if not use_sonic else 'Vp', 'unit': vp_unit}
            y_data = y_depth

        elif plot_type in ['VpVs-bd', 'VpVs-tvd']:
            x_data = vp / vs
            xtempl = {'full_name': 'Vp/Vs', 'unit': '-'}
            y_data = y_depth

        elif plot_type in ['AI-bd', 'AI-tvd']:
            x_data = vp * rho
            xtempl = {'full_name': 'AI', 'unit': '{} {}'.format(vp_unit, rho_unit)}
            y_data = y_depth

        elif plot_type in ['Rho-bd', 'Rho-tvd']:
            x_data = rho
            xtempl = {'full_name': log_table['Density'], 'unit': rho_unit}
            y_data = y_depth

        elif plot_type == 'Phi-Vp':
            x_data = data[log_table['Porosity']].magnitude
            x_unit = '{:~P}'.format(data[log_table['Porosity']].units)
            y_data = vp
            y_unit = '{}'.format(vp_unit)
            xtempl = {'full_name': 'Porosity', 'unit': x_unit}
            ytempl = {'full_name': 'Vp', 'unit': y_unit}
        elif plot_type in ['Phi-%AI', 'Phi-I', 'Phi-G']:
            _ref = _ref_val_of(ref_val, well.name)
            x_data = data[log_table['Porosity']].magnitude
            x_unit = '{:~P}'.format(data[log_table['Porosity']].units)
            xtempl = {'full_name': 'Porosity', 'unit': x_unit}
            if plot_type == 'Phi-%AI':
                y2_data = vp * rho
                y1_data = _ref[0] * _ref[2]
                y_data = 100 * (y2_data - y1_data) / y1_data
                y_unit = '%'
                ytempl = {'full_name': 'rel. AI', 'unit': y_unit}
            elif plot_type == 'Phi-I':
                y_data = rp.intercept(_ref[0], vp, _ref[2], rho)
                y_unit = '-'
                ytempl = {'full_name': 'Intercept', 'unit': y_unit}
            else:
                y_data = rp.gradient(_ref[0], vp, _ref[1], vs, _ref[2], rho)
                y_unit = '-'
                ytempl = {'full_name': 'Gradient', 'unit': y_unit}
        elif plot_type == 'I-G':
            _ref = _ref_val_of(ref_val, well.name)
            x_data = rp.intercept(_ref[0], vp, _ref[2], rho)
            x_unit = '-'
            y_data = rp.gradient(_ref[0], vp, _ref[1], vs, _ref[2], rho)
            y_unit = '-'
            xtempl = {'full_name': 'Intercept', 'unit': x_unit}
            ytempl = {'full_name': 'Gradient', 'unit': y_unit}
        else:
            raise ValueError('No known plot type selected: {}'.format(plot_type))

        # arrange coloring, from the style of the well when set, else from the default cycles
        # crossplot.plot() takes a color which is not a string as data to color by, so use the hex string
        this_color = well.style.fill_color or well.style.line_color or \
            to_hex(xp.cnames[counter % len(xp.cnames)])
        this_marker = well.style.marker or xp.msymbols[counter % len(xp.msymbols)]
        well_styles.append((well.name, this_color, this_marker))
        draw_color_bar = False
        ctempl = None
        if isinstance(color_by, str):
            this_color = data[log_table[color_by]].magnitude
            ctempl = _template_of(well, log_table[color_by], data[log_table[color_by]].units)
            # only draw colorbar for last well
            if counter == len(wells) - 1:
                draw_color_bar = None
        p_data = None
        ptempl = None
        if isinstance(size_by, str):
            p_data = data[log_table[size_by]].magnitude
            ptempl = _template_of(well, log_table[size_by], data[log_table[size_by]].units)

        # start plotting

        cbar = xp.plot(
            x_data,
            y_data,
            cdata=this_color,
            cbar=draw_color_bar,
            mdata=this_marker,
            pdata=p_data,
            xtempl=xtempl,
            ytempl=ytempl,
            ctempl=ctempl,
            ptempl=ptempl,
            mask=mask,
            ax=ax,
            **kwargs
        )
    ax.autoscale(True, axis='both')
    if ('tvd' in plot_type) or ('bd' in plot_type):
        ax.set_ylim(ax.get_ylim()[::-1])
    ax.set_title('{}, {}'.format(wi_name, cutoffs))
    #
    if legend_items is None:
        legend_items = []
        for wname, color, marker in well_styles:
            legend_items.append(
                Line2D([0], [0],
                       color=color,
                       lw=0, marker=marker,
                       label=wname))

    legend_names = [x._label for x in legend_items]
    this_legend = ax.legend(
        legend_items,
        legend_names,
        prop=FontProperties(size='smaller'),
        scatterpoints=1,
        markerscale=2,
        loc=1)

    if savefig is not None:
        fig.savefig(savefig)

    return cbar, this_legend


def plot_rpt(t, rpt, constants, rpt_keywords, sizes, colors, fig=None, ax=None, **kwargs):
    """
    Plot any RPT (rock physics template) that can be described by a function rpt(t), which can be
    evaluated at different values of a constant (eg. the saturation). E.G. rpt(x, const=constants[i])
    E.G. to plot a RPT which is a function of porosity in a Vp/Vs x AI crossplot:
        t = porosity
        x, y = rpt(t)  # x is AI, y is Vp/Vs

    :param t:
        np.array
        array of length N
        t values used to draw the rockphysics template, preferably less than about 10 items long for creating
        nice plots
    :param rpt:
        function
        Rock physics template function of t
        Should take a second argument which is used to parameterize the function
        e.g.
        def rpt(t, c, **rpt_keywords):
            return c*t + rpt_keywords.pop('zero_crossing', 0)
    :param constants:
        list
        list of length M of constants used to parametrize the rpt function
    :param rpt_keywords:
        dict
        Dictionary with keywords passed on to the rpt function
    :param sizes:
        float or np.array (of size N, or M x N)
        determines the size of the markers
        if np.array it must be same size as x
    :param colors
        str or np.array
        determines the colors of the markers
        if np.array it must be same size as x
    :return
        all_x, all_y
        lists of len(constants) ndarray's of x and y data that can be used to
        annotate the plot
    """
    #
    # some initial setups
    all_x = []
    all_y = []
    lw = kwargs.pop('lw', 0.5)
    tc = kwargs.pop('c', 'k')
    edgecolor = kwargs.pop('edgecolor', 'none')
    for test_obj, def_val in zip([sizes, colors], [90., 'red']):
        if test_obj is None:
            test_obj = def_val
        elif isinstance(test_obj, np.ndarray):
            if len(test_obj.shape) == 1:
                # Broadcast 1D array so that it can reused for all elements in constants
                test_obj = np.broadcast_to(test_obj, (len(constants), len(test_obj)))
            elif len(test_obj.shape) == 2:
                if not test_obj.shape == (len(constants), len(t)):
                    raise IOError('Shape of input must match constants, and t: ({}, {})'.format(len(constants), len(t)))
        if def_val == 90.:
            sizes = test_obj
        else:
            colors = test_obj

    #
    # set up plotting environment
    if fig is None:
        if ax is None:
            fig = plt.figure(figsize=(10, 10))
            ax = fig.subplots()
        else:
            fig = ax.get_figure()
    elif ax is None:
        ax = fig.subplots()

    #
    # start drawing the RPT
    if not isinstance(colors, str):
        vmin = np.min(colors)
        vmax = np.max(colors)
        cmap = 'jet'
    else:
        vmin = None; vmax = None; cmap = None
    for i, const in enumerate(constants):
        x, y = rpt(t, const, **rpt_keywords)
        all_x.append(x)
        all_y.append(y)
        # First draw lines of the RPT
        ax.plot(x, y, lw=lw, c=tc, label='_nolegend_', **kwargs)
        # Next draw the points
        ax.scatter(x, y, c=colors if isinstance(colors, str) else colors[i],
                   s=sizes[i] if isinstance(sizes, np.ndarray) else float(sizes),
                   vmin=vmin, vmax=vmax, cmap=cmap, edgecolor=edgecolor,
                   label='_nolegend_', **kwargs)

    return all_x, all_y


def rpt_phi_sw(_phi, _sw, **kwargs):
    """
    Useful rock physics template that can return elastic properties (e.g. AI, Vp/Vs) for many
    different rock physics functions (constant cement, contact cement, stiff sand, soft sand)
    from the input variables _phi and _sw (porosity and water saturation)

    """
    plot_type = kwargs.pop('plot_type', 'AI-VpVs')  # when 'elastics' is used, this function returns vp, vs, rho
    ref_val = kwargs.pop('ref_val', None)  # ref values of Vp, Vs and rho for calculating I x G [Vp, Vs, rho]
    model = kwargs.pop('model', 'stiff')
    phi_c = kwargs.pop('phi_c', None)  # critical porosity
    p_conf = kwargs.pop('p_conf', None)  # Confining pressure in MPa (effective pressure?)
    smcf = kwargs.pop('smcf', None)  # shear modulus correction factor  (1=dry pack with perfect adhesion, 0=dry frictionless pack)
    rho_b = kwargs.pop('rho_b', None)  # Brine density  g/cm3
    k_b = kwargs.pop('k_b', None)   # Brine bulk modulus  GPa
    rho_hc = kwargs.pop('rho_hc', None)  # HC density
    k_hc = kwargs.pop('k_hc', None)  # HC bulk modulus
    rho_min = kwargs.pop('rho_min', None)  # Density [g/cm3] of mineral mix
    k_min = kwargs.pop('k_min', None)  # Bulk modulus GPa of mineral mix
    mu_min = kwargs.pop('mu_min', None)  # Shear modulus of mineral mix
    rho_qz = kwargs.pop('rho_qz', None)  # Density [g/cm3] of quartz
    k_qz = kwargs.pop('k_qz', None)  # Bulk modulus GPa of quartz
    mu_qz = kwargs.pop('mu_qz', None)  # Shear modulus of quartz
    vsh = kwargs.pop('vsh', None)  # Volume fraction of shale
    rho_sh = kwargs.pop('rho_sh', None)  # Density [g/cm3] of shale
    k_sh = kwargs.pop('k_sh', None)  # Bulk modulus GPa of shale
    mu_sh = kwargs.pop('mu_sh', None)  # Shear modulus of shale
    ntg = kwargs.pop('ntg', 1)  # Net to Gross, use the shale properties above in the non-Net
    c_n = kwargs.pop('c_n', None)  # Coordination number in the contact cement model
    k_cem = kwargs.pop('k_cem', None)  # Cement bulk modulus in GPa
    mu_cem = kwargs.pop('mu_cem', None)  # Cement shear modulus in GPa
    scheme = kwargs.pop('scheme', None)  # scheme for calculating cement deposition
    apc = kwargs.pop('apc', None)  # absolute percent cement (in %)
    calc_phi_eff = kwargs.pop('calc_phi_eff', False)  # set this to True to calculate effective porosity and use it

    # Check if we need to calculate the average mineral properties, or if they are given
    if (rho_min is None) or (mu_min is None) or (k_min is None):
        k_min = rp.vrh_bounds([vsh, 1 - vsh], [k_sh, k_qz])[2]  # Mineral bulk modulus
        mu_min = rp.vrh_bounds([vsh, 1 - vsh], [mu_sh, mu_qz])[2]  # Mineral shear modulus
        rho_min = rp.vrh_bounds([vsh, 1 - vsh], [rho_sh, rho_qz])[0]  # Density of minerals

    if calc_phi_eff:
        #phi = _phi - vsh * ((rho_min - rho_sh) / (rho_min - rho_b))  # eq. 2 in https://link.springer.com/article/10.1007/s13202-020-01073-2#Fig8
        phi = _phi * (1. - vsh)  # eq. 1.4 in https://www.informit.com/articles/article.aspx?p=1626870&seqNum=2
    else:
        phi = 1. * _phi

    # Apply the rock physics model to modify the mineral properties
    if model == 'stiff':
        k_dry, mu_dry = rp.stiffsand(k_min, mu_min, phi, phi_c, c_n, p_conf, smcf)
    elif model == 'contactcement':
        k_dry, mu_dry = rp.contactcement(k_min, mu_min, phi, phi_c, c_n, k_cem, mu_cem, scheme)
    elif model == 'constantcement':
        k_dry, mu_dry = rp.constantcement(k_min, mu_min, phi, phi_c, apc, c_n, k_cem, mu_cem, scheme, smcf=smcf)
    else:
        model = 'soft'
        k_dry, mu_dry = rp.softsand(k_min, mu_min, phi, phi_c, c_n, p_conf, smcf)
    info_txt = 'Using {} rock physics template'.format(model)
    print_info(info_txt, 'info', logger)

    # Calculate the final fluid properties for the given water saturation
    print(_sw, k_b, k_hc)
    k_f2 = rp.vrh_bounds([_sw, 1.-_sw], [k_b, k_hc])[1]  # K_f
    rho_f2 = rp.vrh_bounds([_sw, 1.-_sw],  [rho_b, rho_hc])[0]  #RHO_f

    # Use Gassman to calculate the final elastic properties
    vp_2, vs_2, rho_2, k_2 = rp.vels(k_dry, mu_dry, k_min, rho_min, k_f2, rho_f2, phi)

    # if ntg is not 1, the final values are modified with the harmonic mean of the Net to Gross properties
    if ntg != 1:
        vp_2 = rp.vrh_bounds([ntg, 1.-ntg], [vp_2, 1000. * rp.v_p(k_sh, mu_sh, rho_sh)])[1]
        vs_2 = rp.vrh_bounds([ntg, 1.-ntg], [vs_2, 1000. * rp.v_s(mu_sh, rho_sh)])[1]
        rho_2 = rp.vrh_bounds([ntg, 1.-ntg], [rho_2, rho_sh])[1]
        k_2 = rp.vrh_bounds([ntg, 1.-ntg], [k_2, k_sh])[1]

    if plot_type == 'AI-VpVs':
        xx = rho_2*vp_2
        yy = vp_2/vs_2
    elif plot_type == 'AI-Vp':
        xx = rho_2 * vp_2
        yy = vp_2
    elif plot_type == 'Phi-Vp':
        xx = phi
        yy = vp_2
    elif plot_type == 'I-G':
        if ref_val is None:
            raise IOError('List of Vp, Vs, and density must be provided to calculate I and G')
        xx = rp.intercept(ref_val[0], vp_2, ref_val[2], rho_2)
        yy = rp.gradient(ref_val[0], vp_2, ref_val[1], vs_2, ref_val[2], rho_2)
    elif plot_type == 'elastics':
        return vp_2, vs_2, rho_2
    else:
        raise IOError('No valid plot_type selected')

    return xx, yy


def return_rpt_keywords(prev_rpt_kwargs=None, modify_keys=None, verbose=False):
    """
    Returns a default set of rock physics template keywords if prev_rpt_kwargs is set to None,
    The keywords can be modified using the dict modify_keys
    """
    if prev_rpt_kwargs is None:
        rpt_kwargs = {
            'vsh': 0.2, 'phi_c': 0.4, 'c_n': 8, 'p_conf': 45, 'smcf': 0.3,
            'rho_hc': 0.2, 'k_hc': 0.06,
            'rho_b': 1.02, 'k_b': 2.8,
            'rho_qz': 2.6, 'k_qz': 37, 'mu_qz': 45,
            'rho_sh': 2.6, 'k_sh': 20, 'mu_sh': 10,
            'apc': 10,
            'plot_type': 'AI-VpVs', '_ref_val': None}
    else:
        rpt_kwargs = prev_rpt_kwargs

    # modify selected keyword values
    if modify_keys is not None and isinstance(modify_keys, dict):
        for _key, _value in modify_keys.items():
            rpt_kwargs[_key] = _value

    # Determine mineral properties
    rpt_kwargs['k_min'] = rp.vrh_bounds(
        [rpt_kwargs['vsh'], 1 - rpt_kwargs['vsh']], [rpt_kwargs['k_sh'], rpt_kwargs['k_qz']])[2]  # Mineral bulk modulus
    if verbose:
        print('k_min: {}'.format(rpt_kwargs['k_min']))
    rpt_kwargs['mu_min'] = rp.vrh_bounds(
        [rpt_kwargs['vsh'], 1 - rpt_kwargs['vsh']], [rpt_kwargs['mu_sh'], rpt_kwargs['mu_qz']])[
        2]  # Mineral shear modulus
    if verbose:
        print('mu_min: {}'.format(rpt_kwargs['mu_min']))
    rpt_kwargs['rho_min'] = rp.vrh_bounds(
        [rpt_kwargs['vsh'], 1 - rpt_kwargs['vsh']], [rpt_kwargs['rho_sh'], rpt_kwargs['rho_qz']])[
        0]  # Density of minerals

    return rpt_kwargs


def test():
    from blixt_geo_py.core.project import Project
    wi_name = 'Sand E'

    plot_type = 'AI-VpVs'
    ref_val = [2695., 1340., 2.35]  # Kvitnos shale

    fig, ax = plt.subplots()

    wp = Project(name='MyProject')
    log_table = {'P velocity': 'vp_dry', 'S velocity': 'vs_dry', 'Density': 'rho_dry', 'Porosity': 'phie',
                 'Volume': 'vcl'}
    cutoffs = {'Volume': ['<', 0.4], 'Porosity': ['>', 0.1]}
    wp.load_all_wells()
    wis = wp.load_all_wis()

    # plot the well data in the desired cross plot
    plot_rp(wp.wells, log_table, wis, wi_name, cutoffs,
            plot_type=plot_type, ref_val={_w.name: ref_val for _w in wp.wells}, ax=ax)

    # The rock physics template uses the default mineral properties of return_rpt_keywords()
    phi = np.linspace(0.05, 0.3, 6)
    sw = np.array([0.8, 0.95, 1.])
    sizes = np.empty((sw.size, phi.size))
    colors = np.array([np.ones(6) * 100 * (i + 1) ** 2 for i in range(3)]) / 900.
    # iterate over all phi values
    for i, val in enumerate(phi):
        sizes[:, i] = 10 + (40 * val) ** 2

    xx, yy = plot_rpt(phi, rpt_phi_sw, sw,
                      return_rpt_keywords(
                          modify_keys={'plot_type': plot_type, 'ref_value': ref_val, 'model': 'stiff'}),
                      sizes, colors, ax=ax)

    # Annotate rpt
    dx = 0; dy = 0.0
    plt.text(
        xx[-1][-1] + dx, yy[-1][-1] + dy, '$\\phi={:.02f}$'.format(phi[-1]),
        **opt1)
    plt.text(
        xx[-1][0] + dx, yy[-1][0] + dy, '$\\phi={:.02f}$'.format(phi[0]),
        **opt1)
    for i, _sw in enumerate(sw):
        plt.text(
            xx[i][-1] + dx,
            yy[i][-1] + dy, '$S_w={:.02f}$'.format(_sw),
            **opt2
        )

    plt.show()


if __name__ == '__main__':
    #t = np.linspace(2000, 6000, 6)
    #constants = [0, 1, 2]
    #sizes = np.linspace(100, 200, 6)
    #colors = np.array([np.ones(6)*100*(i+1) for i in range(3)])
    #plot_rpt(t, ex_rpt, constants, {'level': 0}, sizes, colors)
    test()

