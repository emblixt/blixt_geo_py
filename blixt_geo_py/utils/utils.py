"""
Collection of functions from blixt_utils/utils.py and moved here

"""
import logging

import numpy as np


def fix_well_name(well_name):
    if well_name is None:
        return None
    if isinstance(well_name, str):
        return well_name.replace('/', '_').replace('-', '_').replace(' ', '').upper()
    else:
        return None


def isnan(val):
    """
    Can test both numbers and strings if they are nan's.

    :param val:
    :return:
        bool
    """
    if isinstance(val, str):
        return False
    try:
        return np.isnan(val)
    except:
        raise NotImplementedError('Cant handle this input properly')


def print_info(
        text: str,
        level: str,
        logger: logging.Logger,
        verbose=True,
        to_logger=True,
        raiser: str | None = None
):
    """
    Prints a string to standard output when verbose is True, and to logger, and can raise errors

    :param text:
        str
        The text that should be printed
    :param level:
        str
        'info', 'warning', 'debug', 'error', 'exception'
    :param logger:
        Logger
        Logger that handel the information. See arrange_logging
    :param verbose:
        bool
        Default True
    :param to_logger:
        bool
        Default True
    :param raiser:
        str
        If provided, the type of error that should be raised
    :return:
    """
    if verbose:
        print('{}: {}'.format(level.upper(), text))
    if to_logger:
        if level.lower() in ['info', 'information']:
            logger.info(text)
        elif level.lower() == 'warning':
            logger.warning(text)
        elif level.lower() == 'debug':
            logger.debug(text)
        elif level.lower() == 'error':
            logger.error(text)
        elif level.lower() == 'exception':
            logger.exception(text)
        else:
            raise IOError('Logger level: {}, not recognized'.format(level.upper()))
    if raiser is not None:
        if raiser.lower() == 'ioerror':
            raise(IOError(text))
        elif raiser.lower() == 'notimplementederror':
            raise(NotImplementedError(text))
        elif raiser.lower() == 'oserror':
            raise (OSError(text))
        elif raiser.lower() == 'typeerror':
            raise(TypeError(text))

def get_from_template(template_dict: dict):
    """

    :param template_dict:
        A template dictionary for a specific logtype, e.g. default_templates['Resistivity']
    :return:
        label, limits, line_style, plot_style
    """
    label = ''
    limits = [None, None]
    line_style = {'lw': None, 'color': None, 'ls': None}
    plot_style = {'cmap': None, 'cnt': None, 'bnds': None, 'scale': None}

    if template_dict is None:
        return label, limits, line_style, plot_style

    key_list = list(template_dict.keys())

    try:
        if 'full_name' in key_list:
            label += template_dict['full_name']
    except TypeError:
        if 'name' in key_list:
            label += template_dict['name']

    if 'unit' in key_list:
        label += ' [{}]'.format(template_dict['unit'])
    elif 'units' in key_list:
        label += ' [{}]'.format(template_dict['units'])
    if 'min' in key_list:
        try:
            limits[0] = float(template_dict['min'])
        except TypeError:
            limits[0] = None
    if 'max' in key_list:
        try:
            limits[1] = float(template_dict['max'])
        except TypeError:
            limits[1] = None

    if 'line width' in key_list:
        line_style['lw'] = template_dict['line width']
    if 'line color' in key_list:
        line_style['color'] = template_dict['line color']
    if 'line style' in key_list:
        line_style['ls'] = template_dict['line style']

    if 'colormap' in key_list:
        plot_style['cmap'] = template_dict['colormap']
    if 'center' in key_list:
        plot_style['cnt'] = template_dict['center']
    if 'bounds' in key_list:
        plot_style['bnds'] = template_dict['bounds']
    if 'scale' in key_list:
        plot_style['scale'] = template_dict['scale']

    return label, limits, line_style, plot_style



