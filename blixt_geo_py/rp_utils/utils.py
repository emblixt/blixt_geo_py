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


