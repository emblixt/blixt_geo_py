import numpy as np
from scipy.optimize import least_squares
import matplotlib.pyplot as plt
from numpy.random import default_rng
import typing
import logging

from blixt_geo_py.misc import masks as msks

logger = logging.getLogger(__name__)


def residuals(x, t, y, target_function=None, weight=None, kwargs=None):
    """
    Returns the residual between the target function and the observed data y
    for a given weight.

    :param x:
        parameters passed to the target function
    :param t:
        np array of length N
        time, or X-axis (independent variable)
          OR
        a (2,N) array
        where N is the total number of data points in y
    :param y:
        np array of length N
        observed data
    :param target_function:
        function to calculate the residual against
            residual = target_function(t, *x) - y
        target_function takes x as arguments, and t as independent variable,
        E.G. for a linear target function:
        def target_function(t, a, b):
            return a*t + b
    :param weight:
        np array of length N
        weights between 0 and 1
        or None
    :param kwargs:
        dictionary
        keywords passed to the target function
    :return:
        np array of length N of residuals
    """
    if kwargs is None:
        kwargs = {}
    if target_function is None:
        raise TypeError('function must be provided to return a residual')

    if len(t.shape) == 2 and t.shape[0] == 2:  # 2D case
        t1, t2 = t
    else:  # assume standard 1D case
        t1 = t; t2 = None

    if weight is None:
        weight = np.ones(t1.shape)
    elif np.nanmin(weight) < 0.:
        raise ValueError('Weights should be larger than 0.')
    elif np.nanmax(weight) > 1.:
        raise ValueError('Weights should not be larger than 1.')
    elif weight.shape != y.shape:
        raise ValueError('Weights must have same dimension as input data')

    if len(t.shape) == 2 and t.shape[0] == 2:  # 2D case
        return weight*(target_function(t1, t2, *x, **kwargs) - y)
    else:  # assume standard 1D case
        return weight * (target_function(t1, *x, **kwargs) - y)


def gen_test_data(x, t, target_function=None, noise=0., n_outliers=0, seed=None):
    """

    :param x:
    :param t:
    :param target_function:
    :param noise:
    :param n_outliers:
    :param seed:
    :return:
    """
    rng = default_rng(seed)
    y = target_function(t, *x)
    y_mean = np.nanmean(y)
    error = noise * rng.standard_normal(t.size)
    outliers = rng.integers(0, t.size, n_outliers)
    error[outliers] *= 10

    return y + error


def linear_function(_t, _a, _b):
    # The linear fitting function
    return _a*_t + _b


def exp_function(_t, _a, _b, _c):
    return _a + _b * np.exp(_c * _t)


def depth_trend(_t, _vp_top, _vp_matrix, _b):
    # Vp depth trend often used by Ikon Science
    # _t is TVD
    return _vp_matrix - (_vp_matrix - _vp_top) * np.exp(-1. * _b * _t)


def calculate_depth_trend(
        y: np.ndarray,
        z: np.ndarray,
        trend_function: typing.Callable,
        x0: list,
        loss: str | None = None,
        mask: np.ndarray | None = None,
        discrete_intervals: list | None = None,
        down_weight_outliers: bool = False,
        ax=None,
        verbose: bool = False,
        title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None
) -> list:
    """

    :param y:
        data to calculate the depth trend for
    :param z:
        depth data
    :param trend_function:
        function
        Function to calculate the residual against
            residual = target_function(z, *x) - y
        trend_function takes x as arguments, and depth as independent variable,
        E.G. for a linear target function:
        def trend_function(depth, a, b):
            return a*depth + b
    :param x0:
        List of parameters values used initially in the trend_function in the optimization
    :param loss:
        Keyword passed on to least_squares() to determine which loss function to use
    :param mask:
        boolean numpy array of length N
        A False value indicates that the data is masked out
    :param discrete_intervals:
        list of depth values at which the trend function are allowed discrete jumps
        Typically the depth of the boundaries between two intervals (formations) in a well.
    :param down_weight_outliers:
        If True, a weighting is calculated to minimize the impact of data far away from the median.
    :param ax:
    :param verbose:
    :param title:
    :param xlabel:
    :param ylabel:

    :return:
        list of arrays with optimized parameters,
        e.g.
        [ array([a0, b0, ...]), array([a1, b1, ...]), ...]
        where [a0, b0, ...] are the output from least_squares for the first interval, and so on
    """
    from blixt_utils.utils import print_info
    if loss is None:
        loss = 'cauchy'
    if mask is None:
        mask = np.array(np.ones(len(y)), dtype=bool)  # All True values -> all data is included
    verbosity_level = 0
    results = []
    # if discrete_intervals is not None:
    #     # calculate the indexes of where the smoothened log are allowed discrete jumps.
    #     discrete_indexes = [np.argmin((z[mask] - _z) ** 2) for _z in discrete_intervals]

    if verbose:
        verbosity_level = 0
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 10))
        ax.scatter(y, z, c='grey')
        if discrete_intervals is not None:
            for _depth in discrete_intervals:
                ax.axhline(_depth, 0, 1, ls='--')

    def do_the_fit(_mask):
        weights = None

        # Test if there are NaN values in input data, which needs to be masked out
        if np.any(np.isnan(y[_mask])):
            nan_mask = np.isnan(y)
            _mask = msks.combine_masks([~nan_mask, _mask])

        # Test if there are infinite values in input data, which needs to be masked out
        if np.any(np.isinf(y[_mask])):
            inf_mask = np.isinf(y)
            _mask = msks.combine_masks([~inf_mask, _mask])

        if down_weight_outliers:
            # weights = 1. - np.sqrt((y[_mask] - np.nanmedian(y[_mask])) ** 2)
            weights = outlier_weights(y, _mask)
            weights[weights < 0] = 0.

        try:
            _res = least_squares(residuals, x0, args=(z[_mask], y[_mask]),
                                 kwargs={'target_function': trend_function, 'weight': weights},
                                 loss=loss, verbose=verbosity_level)

            if verbose:
                info_txt = '  * Success: {}\n  * {}\n  * x0: {}\n  * x: {}'.format(
                    _res['success'], _res['message'], x0, _res['x']
                )
                print_info(info_txt, '', None, verbose, False)

        except ValueError as error:
            _res = None
            warn_txt = 'Depth trend could not calculated'
            print_info(warn_txt, 'warning', logger)
            print(error)
            pass

        return _res

    if discrete_intervals is not None:
        for i in range(len(discrete_intervals) + 1):  # always one more section than boundaries between them
            if i == 0:  # first section
                this_depth_mask = msks.create_mask(z, '<', discrete_intervals[i])
            elif len(discrete_intervals) == i:  # last section
                this_depth_mask = msks.create_mask(z, '>=', discrete_intervals[-1])
            else:  # all middle sections
                this_depth_mask = msks.create_mask(
                    z,
                    '><',
                    [discrete_intervals[i - 1], discrete_intervals[i]])
                #  [discrete_intervals[i - 1], discrete_intervals[i] - 1])

            combined_mask = msks.combine_masks([mask, this_depth_mask])
            res = do_the_fit(combined_mask)
            # results.append(res.x)
            results.append(res)
            if verbose:
                this_depth = np.linspace(
                    z[this_depth_mask][0],
                    z[this_depth_mask][-1], 10)
                ax.plot(y[combined_mask], z[combined_mask])
                ax.plot(trend_function(this_depth, *res.x), this_depth, c='b')
    else:
        res = do_the_fit(mask)
        # results.append(res.x)
        results.append(res)
        if verbose:
            # this_depth = np.linspace(z[0], z[-1], 10)
            this_depth = np.linspace(np.nanmin(z), np.nanmax(z), 10)
            ax.scatter(y[mask], z[mask])
            ax.plot(trend_function(this_depth, *res.x), this_depth, c='b')

    if verbose:
        # ax.set_ylim(ax.get_ylim()[::-1])
        if title is None:
            title_txt = 'Trend using {}'.format(trend_function.__name__)
            ax.set_title(title_txt)
        else:
            ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True)

    return results

def calculate_blocking(
        y: np.ndarray,
        z: np.ndarray,
        mask: np.ndarray | None = None,
        discrete_intervals: list | None = None,
        down_weight_outliers: bool = False,
        ax=None,
        verbose: bool = False,
        title: str | None = None,
        xlabel: str | None = None,
        ylabel: str | None = None
) -> list:
    """
    "Blocks" a well log into a set of discrete values (mean, median & std) for each interval within the discrete_intervals
    :param y:
        data to calculate the blocks for
    :param z:
        depth data
    :param mask:
        boolean numpy array of length N
        A False value indicates that the data is masked out
    :param discrete_intervals:
        list of depth values at which the trend function are allowed discrete jumps
        Typically the depth of the boundaries between two intervals (formations) in a well.
    :param down_weight_outliers:
        If True, a weighting is calculated to minimize the impact of data far away from the median.
    :param ax:
    :param verbose:
    :param title:
    :param xlabel:
    :param ylabel:

    :return:
        list of dictionaries with 'mean', 'median', 'std' as keys. One dictionary per discrete interval
        e.g.
        [ {'mean': XXX, 'median': XXX, 'std': XXX}, ... ]
    """
    from blixt_utils.utils import print_info
    if mask is None:
        mask = np.array(np.ones(len(y)), dtype=bool)  # All True values -> all data is included
    verbosity_level = 0
    results = []

    if verbose:
        verbosity_level = 0
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 10))
        ax.scatter(y, z, c='grey')
        if discrete_intervals is not None:
            for _depth in discrete_intervals:
                ax.axhline(_depth, 0, 1, ls='--')

    if discrete_intervals is not None:
        for i in range(len(discrete_intervals) + 1):  # always one more section than boundaries between them
            if i == 0:  # first section
                this_depth_mask = msks.create_mask(z, '<', discrete_intervals[i])
                z0 = np.nanmin(z) - 1.
                z1 = discrete_intervals[i]
            elif len(discrete_intervals) == i:  # last section
                this_depth_mask = msks.create_mask(z, '>=', discrete_intervals[-1])
                z0 = discrete_intervals[-1]
                z1 = np.nanmax(z) + 1.
            else:  # all middle sections
                this_depth_mask = msks.create_mask(
                    z,
                    '><',
                    [discrete_intervals[i - 1], discrete_intervals[i]])
                           #  [discrete_intervals[i - 1], discrete_intervals[i] - 1])
                z0 = discrete_intervals[i-1]
                z1 = discrete_intervals[i]

            res = calculate_one_block(y[mask], z[mask], z0, z1, down_weight_outliers, verbose)
            results.append(res)

            if verbose:
                this_depth = np.linspace(
                    z[this_depth_mask][0],
                    z[this_depth_mask][-1], 10)
                ax.plot(y[this_depth_mask], z[this_depth_mask])
                ax.plot(np.ones(len(this_depth)) * res['median'], this_depth, c='b')
    else:
        res = calculate_one_block(y, z, np.nanmin(z)-1, np.nanmax(z) + 1, down_weight_outliers, verbose)
        results.append(res)
        if verbose:
            this_depth = np.linspace(np.nanmin(z), np.nanmax(z), 10)
            ax.scatter(y[mask], z[mask])
            ax.plot(np.ones(len(this_depth)) * res['median'], this_depth, c='b')

    if verbose:
        if title is None:
            title_txt = 'Original data + blocking'
            ax.set_title(title_txt)
        else:
            ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(True)

    return results


def calculate_one_block(
        y: np.ndarray,
        z: np.ndarray,
        z0: float,
        z1: float,
        down_weight_outliers: bool,
        verbose: bool
):
    """
    Calculates the mean, median, std, ... of the parameter y within z0 & z1 of the independent variable z (depth)

    :param y:
    :param z:
    :param z0:
    :param z1:
    :param down_weight_outliers
    :param verbose:
    :return:
        A dictionary with keys: 'mean', 'median', 'std', ...
    """
    from blixt_utils.utils import print_info
    weights = None
    down_weight_mask = None

    if verbose:
        print('Calculating one blocked value for z between {} and {} (z covers: {}-{})'.format(
            z0, z1, np.nanmin(z), np.nanmax(z)
        ))
    # Create mask for the requested interval
    _mask = msks.create_mask( z, '><', [z0, z1])

    # Test if there are NaN values in input data, which needs to be masked out
    if np.any(np.isnan(y[_mask])):
        nan_mask = np.isnan(y)
        _mask = msks.combine_masks([~nan_mask, _mask])

    # Test if there are infinite values in input data, which needs to be masked out
    if np.any(np.isinf(y[_mask])):
        inf_mask = np.isinf(y)
        _mask = msks.combine_masks([~inf_mask, _mask])

    if down_weight_outliers:
        down_weight_mask = np.array(np.ones(len(y)), dtype=bool)  # All True values -> all data is included
        # weights = 1. - np.sqrt((y - np.nanmedian(y)) ** 2)
        weights = outlier_weights(y)
        down_weight_mask[weights < 0] = False
        _mask = msks.combine_masks([down_weight_mask, _mask])

    try:
        _res = dict(
            min=np.nanmin(y[_mask]),
            max=np.nanmax(y[_mask]),
            mean=np.nanmean(y[_mask]),
            median=np.nanmedian(y[_mask]),
            std=np.nanstd(y[_mask])
        )

        if verbose:
            info_txt = '  * Success:\n    mean: {:.2}, median: {:.2}, std: {:.2}, min: {:.2}, max: {:.2}'.format(
                _res['mean'], _res['median'], _res['std'], _res['min'], _res['max'])

            print_info(info_txt, 'info', logger, verbose )

    except ValueError as error:
        _res = dict(
            min=None,
            max=None,
            mean=None,
            median=None,
            std=None
        )
        warn_txt = 'Blocked values could not calculated, because {}'.format(error)
        print_info(warn_txt, 'warning', logger)
        print(error)
        pass

    return _res

def outlier_weights(y: np.ndarray, mask: np.ndarray | None = None, method: str | None = None) -> np.ndarray:
    """
    Tries to identify outliers.
    Returns a np.ndarray where values below your preferred threshold (typically 0) are considered as outliers in y
    e.g.
    > weights = outlier_weights(y, mask)
    > weights[weights < 0] = 0

    :param y:
    :param mask:
    :param method:
    :return:
    """
    if method is None:
        # TODO: Maybe this method removes to much data?? Try using the std
        if mask is not None:
            weights = 1. - np.sqrt((y[mask] - np.nanmedian(y[mask])) ** 2)
        else:
            weights = 1. - np.sqrt((y - np.nanmedian(y)) ** 2)
    else:
        weights = np.ones(len(y))

    return weights



def play_with_data_fit():
    fig, ax = plt.subplots()

    # Data
    x = [-0.2, 5]  # True parameters of the starting linear function
    # Perturb the linear function with noise
    t = np.linspace(0, 10, 100) + np.random.random(100)  # the independent "time" variable
    y = linear_function(t, *x) + np.random.random(100) - 0.5  # The "observed" data
    # Add data to the dataset through append (out of curiosity)
    t = np.append(t, np.linspace(0, 10, 100) + np.random.random(100))
    y = np.append(y, linear_function(np.linspace(0, 10, 100), *x) + np.random.random(100) - 0.5)

    new_t = np.linspace(0, 10)  # the new independent "time" variable we use to plot the fitted function

    ax.scatter(t, y)

    # initial guess of parameters to the fitting function
    x0 = [1., 1.]

    # least_squares fit with the residual function using the linear function to calculate the error
    res = least_squares(residuals, x0, args=(t, y), kwargs={'target_function': linear_function}, verbose=2)
    res2 = least_squares(residuals, x0, args=(t, y), kwargs={'target_function': linear_function},
                         loss='cauchy', verbose=2)

    # Try with weights
    weights = np.ones(len(t))
    weights[y > 4.5] = 0  # ignore data points above
    weights[y < 3.0] = 0  # ignore data points below
    res3 = least_squares(residuals, x0, args=(t, y), kwargs={'target_function': linear_function, 'weight': weights}, verbose=2)

    print(x); print(res.x); print(res2.x); print(res3.x)

    ax.plot(new_t, linear_function(new_t, *x),
            new_t, linear_function(new_t, *res.x),
            new_t, linear_function(new_t, *res2.x),
            new_t, linear_function(new_t, *res3.x))

    plt.show()


def compare_loss_functions():
    fig, ax = plt.subplots()

    # Generate training data
    # Two blocks of data, shifted in value and "depth"
    a = 3000.
    b = 1500.
    c = -0.03
    t_min_1 = 1000.  # TVD in m
    t_max_1 = 2000.
    n_points = 300
    t_train_1 = np.linspace(t_min_1, t_max_1, n_points)
    y_train_1 = gen_test_data([a, b, c], t_train_1,  target_function=exp_function,
                            noise=4.3, n_outliers=30)

    a = 3500.
    t_min_2 = 3000.  # TVD in m
    t_max_2 = 4000.
    t_train_2 = np.linspace(t_min_2, t_max_2, n_points)
    y_train_2 = gen_test_data([a, b, c], t_train_2,  target_function=exp_function,
                              noise=4.3, n_outliers=30)

    t_train = np.concatenate([t_train_1, t_train_2])
    y_train = np.concatenate([y_train_1, y_train_2])

    ax.plot(t_train, y_train, 'o')

    # Start fitting a curve to the training data
    x0 = [1000., 1000., -0.1]
    t_test = np.linspace(t_min_1, t_max_2, n_points * 10)
    ax.plot(t_test, exp_function(t_test, a, b, c), 'k', linewidth=2, label='true')

    res_lsq = least_squares(residuals, x0,
                            args=(t_train, y_train),
                            kwargs= {'target_function': exp_function}, verbose=0)
    print('Default linear least squares: Success? {}'.format(res_lsq['success']))
    print(' {}'.format(res_lsq['message']))
    print(' x0: ', x0)
    print(' x: ', res_lsq['x'])
    ax.plot(t_test, exp_function(t_test, *res_lsq.x), label='linear loss')

    res_soft_l1 = least_squares(residuals, x0, loss='soft_l1', f_scale=0.1,
                                args=(t_train, y_train),
                                kwargs={'target_function': exp_function}, verbose=0)
    print('Soft L1 norm: Success? {}'.format(res_soft_l1['success']))
    print(' {}'.format(res_soft_l1['message']))
    print(' x0: ', x0)
    print(' x: ', res_soft_l1['x'])
    ax.plot(t_test, exp_function(t_test, *res_soft_l1.x), label='soft l1 loss')

    res_log = least_squares(residuals, x0, loss='cauchy', f_scale=0.1,
                            args=(t_train, y_train),
                            kwargs={'target_function': exp_function}, verbose=0)
    print('Cauchy norm: Success? {}'.format(res_log['success']))
    print(' {}'.format(res_log['message']))
    print(' x0: ', x0)
    print(' x: ', res_log['x'])
    ax.plot(t_test, exp_function(t_test, *res_log.x), 'r--', label='cauchy loss')

    ax.set_xlabel('t')
    ax.set_ylabel('y')
    ax.legend()
    plt.show()


if __name__ == '__main__':
    # play_with_data_fit()
    compare_loss_functions()