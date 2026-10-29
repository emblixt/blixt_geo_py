"""
Collection of functions from blixt_utils/utils.py and moved here

"""
import logging
import sys

import numpy as np

from blixt_geo_py.misc import masks as msks


def fix_well_name(well_name):
    if well_name is None:
        return None
    if isinstance(well_name, str):
        return well_name.replace('/', '_').replace('-', '_').replace(' ', '').upper()
    else:
        return None


def nan_corrcoef(x, y):
    maskx = ~np.ma.masked_invalid(x).mask
    masky = ~np.ma.masked_invalid(y).mask
    mask = msks.combine_masks([maskx, masky], verbose=False)
    return np.corrcoef(x[mask], y[mask])


def find_value(x: np.ndarray, x_index: int, snap_to: str = 'exact') -> (float, int):
    """
    Returns the value of the array x at index position x_index, when 'snap_to' is 'exact'
    But can return the nearest min or max, ... or TODO
    :param x:
    :param x_index:
    :param snap_to:
        'exact': returns (x[x_index], x_index)
        'nearest_min': returns the local minimum closest to x_index and its index
        'nearest_max': returns the local maximum closest to x_index and its index
        'nearest_extreme': returns the local extreme closest to x_index and its index
    :return:
        (value, index_position)
    """
    from scipy.signal import argrelmax, argrelmin
    if snap_to == 'exact':
        return x[x_index], x_index
    elif snap_to == 'nearest_min':
        local_minima = argrelmin(x)[0]
        closest_minima = np.argmin(np.sqrt((local_minima - x_index)**2))
        x_index = local_minima[closest_minima]
        return x[x_index], x_index
    elif snap_to == 'nearest_max':
        local_max = argrelmax(x)[0]
        closest_max = np.argmin(np.sqrt((local_max - x_index)**2))
        x_index = local_max[closest_max]
        return x[x_index], x_index
    elif snap_to == 'nearest_extreme':
        local_minima = argrelmin(x)[0]
        local_max = argrelmax(x)[0]
        closest_minima = np.argmin(np.sqrt((local_minima - x_index)**2))
        closest_max = np.argmin(np.sqrt((local_max - x_index) ** 2))
        if abs(x_index - local_minima[closest_minima]) < abs(x_index - local_max[closest_max]):
            x_index = local_minima[closest_minima]
        else:
            x_index = local_max[closest_max]
        return x[x_index], x_index
    else:
        raise IOError('Unknown snap_to: {}'.format(snap_to))


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


def arrange_logging(log_to_stdout, log_to_this_file, level=logging.INFO):
    """
    :param log_to_stdout:
        bool
        If True, the logging is output to stdout
    :param log_to_this_file:
    :param level:
    :return:
    """
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        handler.close()  # close the log file of a FileHandler, which otherwise is left open

    frmt = '%(asctime)s | %(filename)s - %(funcName)s: %(levelname)s:%(message)s'
    if log_to_stdout:
        logging.basicConfig(stream=sys.stdout,
                            format=frmt,
                            level=level,
                            datefmt='%Y-%m-%d %H:%M:%S')
    else:
        logfile = log_to_this_file
        logging.basicConfig(filename=logfile,
                            format=frmt,
                            level=level,
                            datefmt='%Y-%m-%d %H:%M:%S')


def log_table_in_smallcaps(log_table):
    for key in list(log_table.keys()):
        if isinstance(log_table[key], list):
            log_table[key] = [_item.lower() for _item in log_table[key]]
        else:
            log_table[key] = log_table[key].lower()
    return log_table


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



