"""
Calculate statistics of well logs within working intervals, across several wells.

Built on the new Well (core.well), LogCurve (core.log_curve) and the helpers in core.core:
    - LogTable maps log types (e.g. 'P velocity') to log names (e.g. 'vp_dry')
    - Cutoffs / CutoffRule select the data (e.g. sands or shales)
    - Intervals hold the top and base of each working interval in each well

Usage:
    wp = Project(name='MyProject', project_table='excels/project_table.xlsx')
    wp.load_all_wells()
    stats = StatsCalculation(wp.wells, wp.load_all_wis(), ['Sand E', 'Sand F'],
                             log_table={'P velocity': 'vp_dry', 'Porosity': 'phie', 'Volume': 'vcl'},
                             cutoffs='Volume<0.5[], Porosity>0.1[]')  # Leave out to use all samples of the intervals
    results = stats.run()
    print(results['Sand E'].summary())
    stats.save_summary(results, 'summary.xlsx')
    stats.plot_logs_vs_depth(results)
    stats.plot_averages(results)
    stats.plot_logs_vs_burial_depth(results)
    print(stats.gardner(results))
    stats.save_gardner(results, 'gardner.xlsx')
    a, b = read_gardner('gardner.xlsx', 'Sand E')
    stats.plot_gardner(results)
    stats.plot_elastics(results)
"""
import logging
import os
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pint

import blixt_geo_py.io.io as uio
from blixt_geo_py import Q_
from blixt_geo_py.core.core import Cutoffs, CutoffRule, Intervals, LogTable
from blixt_geo_py.core.well import Well
from blixt_geo_py.plotting import crossplot as xp
from blixt_geo_py.utils.utils import nan_corrcoef, print_info

logger = logging.getLogger(__name__)

# Log types needed for writing a RokDoc compatible Sums and Averages file
rokdoc_log_types = ['P velocity', 'S velocity', 'Density', 'Porosity', 'Volume']

# The published coefficients of the Gardner equation, for Vp in m/s and density in g/cm3
gardner_a = 0.31
gardner_b = 0.25


def to_cutoffs(cutoffs: Cutoffs | str | dict | None) -> Cutoffs:
    """
    Returns a Cutoffs object from any of the supported input formats

    :param cutoffs:
        Cutoffs
        or str, e.g. "Volume<0.5[], Porosity>0.1[]"
        or dict (old style) with log types as keys, and list with mask definition as value
            E.G. {'Volume': ['<', 0.5], 'Porosity': ['>', 0.1]}
            The limits are then taken as dimensionless
        or None, which means no cutoffs
    """
    if cutoffs is None:
        return Cutoffs(cutoffs=[])
    if isinstance(cutoffs, Cutoffs):
        return cutoffs
    if isinstance(cutoffs, str):
        return Cutoffs(from_string=cutoffs)
    if isinstance(cutoffs, dict):
        rules = []
        for _param, _definition in cutoffs.items():
            if not isinstance(_definition, (list, tuple)) or len(_definition) != 2:
                raise TypeError('A dict of cutoffs must be {{log type: [operator, limit]}}, not {{{!r}: {!r}}}. If '
                                'this is a log table: log_table comes before cutoffs in StatsCalculation()'.format(
                                    _param, _definition))
            _operator, _limit = _definition
            if isinstance(_limit, (list, tuple)):
                _limit = [_x if isinstance(_x, pint.Quantity) else Q_(_x, '') for _x in _limit]
            elif not isinstance(_limit, pint.Quantity):
                _limit = Q_(_limit, '')
            rules.append(CutoffRule(_param, _operator, _limit))
        return Cutoffs(cutoffs=rules)
    raise TypeError('cutoffs must be a Cutoffs, str, dict or None, not {}'.format(type(cutoffs)))


def _per_interval(value, n: int, name: str, single_types: tuple) -> list:
    """
    Expands a single value to one value per working interval, or checks that a list has one value per interval
    """
    if isinstance(value, single_types) or value is None:
        return [value] * n
    if isinstance(value, list):
        if len(value) != n:
            raise ValueError('The number of {}, {}, must be same as number of working intervals, {}'.format(
                name, len(value), n))
        return value
    raise TypeError('{} must be a single value or a list, not {}'.format(name, type(value)))


def break_at_gaps(values: np.ndarray, depth: np.ndarray, factor: float = 1.5) -> tuple:
    """
    Inserts a NaN in both arrays wherever the depth step is larger than factor times the median step,
    so a line plot is broken where the cutoffs have removed samples, instead of bridging the gap

    :param values:
        np.ndarray
    :param depth:
        np.ndarray, increasing
    :param factor:
        float
        A depth step larger than factor times the median step counts as a gap
    :return:
        values, depth
    """
    if len(depth) < 3:
        return values, depth
    steps = np.diff(depth)
    gaps = np.nonzero(steps > factor * np.median(steps))[0] + 1
    return (np.insert(values.astype(float), gaps, np.nan),
            np.insert(depth.astype(float), gaps, np.nan))


def isolated_samples(values: np.ndarray, depth: np.ndarray) -> np.ndarray:
    """
    Returns a boolean mask which is True for samples without a valid neighbour on either side.
    A line plot doesn't draw these, so they need a marker to show up

    :param values:
        np.ndarray, e.g. from break_at_gaps()
    :param depth:
        np.ndarray, e.g. from break_at_gaps()
    :return:
        np.ndarray of bool
    """
    valid = ~np.isnan(values) & ~np.isnan(depth)
    has_previous = np.r_[False, valid[:-1]]
    has_next = np.r_[valid[1:], False]
    return valid & ~has_previous & ~has_next


def linear_depth_trend(values: np.ndarray, depth: np.ndarray) -> dict | None:
    """
    Fits a straight line through the values as a function of depth, by least squares through all valid samples

    :param values:
        np.ndarray
    :param depth:
        np.ndarray of the same length as values
    :return:
        dict or None
        {'slope': change of the values per unit of depth,
         'intercept': the value at depth = 0,
         'r2': the fraction of the variance of the values that the trend explains,
         'std': standard deviation of the values,
         'std_detrended': standard deviation of the values around the trend,
         'n': number of valid samples}
        None if there are less than three valid samples, or if they are all at the same depth
    """
    valid = np.isfinite(values) & np.isfinite(depth)
    if np.sum(valid) < 3 or np.ptp(depth[valid]) == 0.:
        return None
    _values, _depth = values[valid], depth[valid]
    slope, intercept = np.polyfit(_depth, _values, 1)
    std = np.std(_values)
    std_detrended = np.std(_values - (slope * _depth + intercept))
    return {'slope': slope, 'intercept': intercept,
            # Not testing std, which rounding can leave slightly above zero for constant values
            'r2': 1. - (std_detrended / std) ** 2 if np.ptp(_values) > 0. else 0.,
            'std': std, 'std_detrended': std_detrended, 'n': int(np.sum(valid))}


def _valid_vp_and_rho(vp: np.ndarray, rho: np.ndarray) -> np.ndarray:
    return np.isfinite(vp) & np.isfinite(rho) & (vp > 0.) & (rho > 0.)


def fit_gardner(vp: np.ndarray, rho: np.ndarray) -> dict | None:
    """
    Calibrates the Gardner equation, rho = a * vp ** b, by a linear regression of its natural logarithm:
        ln(rho) = ln(a) + b * ln(vp)
    Samples that are not finite, or not positive, are ignored

    :param vp:
        np.ndarray
        P velocity. The value of a depends on the units, see gardner_a
    :param rho:
        np.ndarray
        Density, of the same length as vp
    :return:
        dict or None
        {'a': the coefficient,
         'b': the exponent,
         'r2': the fraction of the variance of ln(rho) that the fit explains,
         'n': number of valid samples}
        None if there are less than three valid samples, or if they all have the same velocity
    """
    valid = _valid_vp_and_rho(vp, rho)
    if np.sum(valid) < 3 or np.ptp(vp[valid]) == 0.:
        return None
    ln_vp, ln_rho = np.log(vp[valid]), np.log(rho[valid])
    b, ln_a = np.polyfit(ln_vp, ln_rho, 1)
    return {'a': np.exp(ln_a), 'b': b,
            # Not testing the std, which rounding can leave slightly above zero for a constant density
            'r2': 1. - (np.std(ln_rho - (b * ln_vp + ln_a)) / np.std(ln_rho)) ** 2 if np.ptp(ln_rho) > 0. else 0.,
            'n': int(np.sum(valid))}


def read_gardner(file_name: str, wi_name: str, suffix: str = '', well: str = 'All') -> tuple:
    """
    Reads the coefficients of the Gardner equation, rho = a * vp ** b with vp in m/s and rho in g/cm3, from a file
    written by StatsCalculation.save_gardner()

    :param file_name:
        str
        full pathname of the excel file
    :param wi_name:
        str
        Name of the working interval
    :param suffix:
        str
        The suffix used for the working interval. Leave out if it had none
    :param well:
        str
        Name of the well, or 'All' for all wells together
    :return:
        a, b
        float, float
    """
    # Empty text must stay empty, so that an interval without a suffix can be found, and a well named e.g. 'NA' is kept.
    # Only the coefficients are NaN when they are empty
    table = pd.read_excel(file_name, keep_default_na=False, na_values={_c: [''] for _c in ['a', 'b', 'r2']})
    rows = table[(table['interval'] == wi_name) & (table['suffix'] == suffix) & (table['well'] == well)]
    description = 'interval {}, suffix "{}" and well {}'.format(wi_name, suffix, well)
    if len(rows) != 1:
        available = sorted({'{}, suffix "{}"'.format(_i, _s) for _i, _s in zip(table['interval'], table['suffix'])})
        raise ValueError('Found {} lines for {} in {}, expected one. The file holds: {}'.format(
            len(rows), description, file_name, '; '.join(available)))
    a, b = float(rows['a'].iloc[0]), float(rows['b'].iloc[0])
    if np.isnan(a) or np.isnan(b):
        raise ValueError('No Gardner coefficients for {} in {}, it has too few samples ({})'.format(
            description, file_name, rows['n'].iloc[0]))
    return a, b


def _log_in_well(data: dict, log_name: str) -> bool:
    return log_name in data and len(data[log_name]) > 0


def _plot_samples_of_well(ax, x: np.ndarray, y: np.ndarray, color: str, marker: str):
    """
    Plots the samples of a well, and their mean with the standard deviation in both directions

    :return:
        The mean with its error bars, to use in a legend
    """
    ax.scatter(x, y, s=4, alpha=0.3, color=color, edgecolors='none', rasterized=True)
    return ax.errorbar(np.mean(x), np.mean(y), xerr=np.std(x), yerr=np.std(y), marker=marker, ms=8, color=color,
                       mec='k', ecolor=color, capsize=4, ls='none', zorder=5)


def _plot_mean_of_all_wells(ax, x: np.ndarray, y: np.ndarray):
    return ax.scatter(np.mean(x), np.mean(y), marker='*', s=220, c='pink', edgecolors='k', zorder=6)


@dataclass
class IntervalStats:
    """
    The masked log data, per well, within one working interval
    """
    wi_name: str
    log_table: LogTable
    cutoffs: Cutoffs
    suffix: str = ''
    per_well: dict = field(default_factory=dict)  # well name -> {log name: pint.Quantity}
    depth_from_top: dict = field(default_factory=dict)  # well name -> pint.Quantity
    burial_depth: dict = field(default_factory=dict)  # well name -> pint.Quantity in meter, for wells where it's known
    project_to_burial_depth: pint.Quantity | None = None  # see StatsCalculation

    @property
    def label(self) -> str:
        return '{}, {}'.format(self.wi_name, self.suffix) if self.suffix else self.wi_name

    @property
    def well_names(self) -> list:
        return list(self.per_well.keys())

    def combined(self) -> dict:
        """
        Returns the data of all wells concatenated, for each log, converted to the units of the first well
        """
        _combined = {}
        for _log in self.log_table.log_names:
            _parts = [_data[_log] for _data in self.per_well.values() if _log in _data]
            if len(_parts) == 0:
                continue
            _units = _parts[0].units
            _combined[_log] = Q_(np.concatenate([_p.to(_units).magnitude for _p in _parts]), _units)
        return _combined

    def samples_with_burial_depth(self, log_name: str) -> tuple:
        """
        Returns the data of the given log, and the burial depth in meter, concatenated over the wells where the
        burial depth is known. The data is converted to the units of the first of these wells

        :return:
            pint.Quantity, np.ndarray
            or None, None if no well has both the log and the burial depth
        """
        _wells = [_w for _w, _data in self.per_well.items()
                  if _log_in_well(_data, log_name) and _w in self.burial_depth]
        if len(_wells) == 0:
            return None, None
        _units = self.per_well[_wells[0]][log_name].units
        return (Q_(np.concatenate([self.per_well[_w][log_name].to(_units).magnitude for _w in _wells]), _units),
                np.concatenate([self.burial_depth[_w].to('m').magnitude for _w in _wells]))

    @property
    def projected_label(self) -> str:
        return 'Projected to {:g} m'.format(self.project_to_burial_depth.to('m').magnitude)

    def burial_depth_trend(self, log_name: str) -> dict | None:
        """
        Returns the linear trend of the given log versus burial depth, through the samples of all wells where the
        burial depth is known, see linear_depth_trend(). None if the trend can't be calculated
        """
        values, depth = self.samples_with_burial_depth(log_name)
        return None if values is None else linear_depth_trend(values.magnitude, depth)

    def projected(self) -> dict:
        """
        Returns the data of all wells where the burial depth is known, for each log, where each sample is moved along
        the linear trend of its log to the burial depth project_to_burial_depth. It is otherwise like combined(), so
        that the mean is the value of the trend at that depth, and the standard deviation is the one around the trend

        :return:
            dict
            {log name: pint.Quantity}
            Only holds the logs with a linear trend, and is empty if project_to_burial_depth is None
        """
        if self.project_to_burial_depth is None:
            return {}
        target = self.project_to_burial_depth.to('m').magnitude
        _projected = {}
        for _log in self.log_table.log_names:
            trend = self.burial_depth_trend(_log)
            if trend is None:
                continue
            values, depth = self.samples_with_burial_depth(_log)
            _projected[_log] = Q_(values.magnitude + trend['slope'] * (target - depth), values.units)
        return _projected

    def vp_and_rho(self) -> dict:
        """
        Returns the P velocity in m/s and the density in g/cm3, for each well that has both, and for these wells
        together ('All')

        :return:
            dict
            {well name: (np.ndarray, np.ndarray)}
            Empty if the log table lacks 'P velocity' or 'Density'
        """
        if 'P velocity' not in self.log_table or 'Density' not in self.log_table:
            return {}
        vp_log, rho_log = self.log_table['P velocity'], self.log_table['Density']
        # Only wells with both logs, so that the samples of 'All' still belong together
        samples = {_well: (_data[vp_log].to('m/s').magnitude, _data[rho_log].to('g/cm**3').magnitude)
                   for _well, _data in self.per_well.items() if vp_log in _data and rho_log in _data}
        if len(samples) > 0:
            samples['All'] = (np.concatenate([_vp for _vp, _ in samples.values()]),
                              np.concatenate([_rho for _, _rho in samples.values()]))
        return samples

    def ai_and_vpvs(self) -> dict:
        """
        Returns the acoustic impedance (Vp * Rho) in km/s*g/cm3 and Vp/Vs, for each well that has the P velocity, S
        velocity and density, and for these wells together ('All'). A zero S velocity gives a non-finite Vp/Vs

        :return:
            dict
            {well name: (np.ndarray, np.ndarray)}
            Empty if the log table lacks 'P velocity', 'S velocity' or 'Density'
        """
        if any(_log_type not in self.log_table for _log_type in ['P velocity', 'S velocity', 'Density']):
            return {}
        vp_log, vs_log, rho_log = [self.log_table[_x] for _x in ['P velocity', 'S velocity', 'Density']]
        samples = {}
        # Only wells with all logs, so that the samples of 'All' still belong together
        for _well, _data in self.per_well.items():
            if vp_log in _data and vs_log in _data and rho_log in _data:
                _vp = _data[vp_log].to('km/s').magnitude
                with np.errstate(divide='ignore', invalid='ignore'):
                    samples[_well] = (_vp * _data[rho_log].to('g/cm**3').magnitude,
                                      _vp / _data[vs_log].to('km/s').magnitude)
        if len(samples) > 0:
            samples['All'] = (np.concatenate([_ai for _ai, _ in samples.values()]),
                              np.concatenate([_vpvs for _, _vpvs in samples.values()]))
        return samples

    def gardner(self) -> pd.DataFrame:
        """
        Returns the Gardner coefficients, rho = a * vp ** b with vp in m/s and rho in g/cm3, per well and for all
        wells together ('All'). They are NaN where there are too few samples, see fit_gardner().
        Note that 'All' mixes wells where the interval may lie at different burial depths
        """
        rows = []
        for _well_name, (_vp, _rho) in self.vp_and_rho().items():
            _fit = fit_gardner(_vp, _rho) or {'a': np.nan, 'b': np.nan, 'r2': np.nan}
            rows.append({'interval': self.wi_name, 'suffix': self.suffix, 'cutoffs': str(self.cutoffs),
                         'well': _well_name, 'n': int(np.sum(_valid_vp_and_rho(_vp, _rho))),
                         'a': _fit['a'], 'b': _fit['b'], 'r2': _fit['r2'],
                         'vp units': 'm/s', 'rho units': 'g/cm3'})
        return pd.DataFrame(rows, columns=['interval', 'suffix', 'cutoffs', 'well', 'n', 'a', 'b', 'r2', 'vp units',
                                           'rho units'])

    def summary(self) -> pd.DataFrame:
        """
        Returns the number of samples, mean, median, standard deviation, P10 and P90 of each log,
        per well, for all wells together ('All') and, with project_to_burial_depth, for all wells projected to that
        burial depth ('Projected to ... m')
        """
        rows = []
        sources = list(self.per_well.items()) + [('All', self.combined())]
        _projected = self.projected()
        if len(_projected) > 0:
            sources.append((self.projected_label, _projected))
        for _well_name, _data in sources:
            for _log_type, _log in self.log_table.items():
                if _log not in _data:
                    continue
                _values = _data[_log].magnitude
                rows.append({
                    'interval': self.wi_name, 'suffix': self.suffix, 'well': _well_name, 'log type': _log_type,
                    'log': _log,
                    'units': str(_data[_log].units), 'n': int(np.sum(~np.isnan(_values))),
                    'mean': np.nanmean(_values), 'median': np.nanmedian(_values), 'std': np.nanstd(_values),
                    'p10': np.nanpercentile(_values, 10), 'p90': np.nanpercentile(_values, 90)
                })
        return pd.DataFrame(rows)


def _lacking_burial_depth(results: dict) -> list:
    """
    Returns the names of the wells with data, but without the burial depth, in any of the given results
    """
    wells = []
    for stats in results.values():
        wells += [_w for _w in stats.per_well if _w not in stats.burial_depth and _w not in wells]
    return wells


def collect_interval_stats(wells: list,
                           intervals: Intervals,
                           wi_name: str,
                           log_table: LogTable,
                           cutoffs: Cutoffs,
                           suffix: str = '') -> IntervalStats:
    """
    Collects the log data within the given working interval in each well, which also pass the cutoffs

    :param wells:
        list of Well
    :param intervals:
        Intervals
        Working intervals, e.g. from Project.load_all_wis()
    :param wi_name:
        str
        Name of the working interval
    :param log_table:
        LogTable
        The log types, and which log to use for each type
    :param cutoffs:
        Cutoffs
        Rules may refer to log types (e.g. 'Volume') or log names (e.g. 'vcl')
    :param suffix:
        str
        Tags the results, e.g. 'sands'
    :return:
        IntervalStats
    """
    log_table = log_table.single_log()
    # Convert rules on log types (e.g. 'Volume') to rules on log names (e.g. 'vcl')
    rules = cutoffs.use_log_table(log_table).cutoffs
    stats = IntervalStats(wi_name=wi_name, log_table=log_table, cutoffs=cutoffs, suffix=suffix)

    for well in wells:
        # Don't use Intervals.get_cutoff_rule(), which falls back to the whole well when the interval is missing
        interval = intervals.get_interval(wi_name, well.name)
        if interval is None:
            print_info('Interval {} not present in {}'.format(wi_name, well.name), 'info', logger)
            continue

        missing = [_log for _log in log_table.log_names if _log not in well.get_log_names]
        if len(missing) > 0:
            print_info('Well {} lacks the logs: {}'.format(well.name, ', '.join(missing)), 'warning', logger)

        # The depth is needed both for the interval rule and the depth from top
        if 'md' not in well.get_log_names:
            well.create_md_log()
        # Wells without a TVD log can't have a burial depth, plot_logs_vs_burial_depth() reports those
        if 'tvd_ml' not in well.get_log_names and len(well.get_logs_of_type('TVD')) > 0:
            well.create_tvd_ml_log()

        # Build a new Cutoffs for each well, so the interval rule is not added to the users cutoffs
        well_cutoffs = Cutoffs(cutoffs=deepcopy(rules) +
                               [CutoffRule('md', '><', [interval.top, interval.base])])
        _data = well.dict(cutoffs=well_cutoffs, use_cutoffs=True)

        stats.per_well[well.name] = {_log: _data[_log] for _log in log_table.log_names if _log in _data}
        stats.depth_from_top[well.name] = interval.distance_to_top(_data['md'])
        # The burial depth is NaN when the kelly bushing or water depth is lacking in the project table.
        # An interval without samples says nothing about that
        if 'tvd_ml' in _data and (len(_data['tvd_ml']) == 0 or np.any(np.isfinite(_data['tvd_ml'].magnitude))):
            stats.burial_depth[well.name] = _data['tvd_ml'].to('m')
        print_info('Interval {} in well {}: {} samples within {:.1f} - {:.1f}'.format(
            wi_name, well.name, len(_data['md']), interval.top, interval.base), 'info', logger)

    return stats


class StatsCalculation:
    """
    Calculates the statistics of the given logs across all wells, for each of the working intervals
    """
    def __init__(self,
                 wells: list | dict,
                 intervals: Intervals,
                 wi_names: str | list,
                 log_table: LogTable | dict | list,
                 cutoffs: Cutoffs | str | dict | list | None = None,
                 suffix: str | list = '',
                 working_dir: str | None = None,
                 project_to_burial_depth: pint.Quantity | None = None):
        """
        :param wells:
            list of Well, or dict of Well
            e.g.
                wp = Project(...)
                wp.load_all_wells()
                wells = wp.wells
        :param intervals:
            Intervals
            e.g. wp.load_all_wis()
        :param wi_names:
            str or list of working interval names
            An interval can be repeated, e.g. to use different cutoffs for sand and shale, if each has its own suffix
        :param log_table:
            LogTable or dict of {log type: log name}, or a list of these, one per working interval
            The P velocity, S velocity, Density, Porosity and Volume logs are needed for the RokDoc output
            If a log type has several logs (multi log LogTable), the user is asked which log to use
        :param cutoffs:
            Cutoffs, str (e.g. "Volume<0.5[], Porosity>0.1[]"), dict (e.g. {'Volume': ['<', 0.5]}) or None
            None uses all samples of the working interval, regardless of lithology
            If a single value, it is used in all working intervals
            If it is a list, it must have the same length as wi_names
        :param suffix:
            str or list of strings
            Tags the results of each working interval
        :param working_dir:
            str
            Folder where the figures are saved
        :param project_to_burial_depth:
            pint.Quantity of length
            If given, there is one extra set of statistics per interval, similar to 'All': The samples of all wells
            where the burial depth is known are moved along the linear trend of each log versus burial depth, to this
            burial depth, before the statistics are calculated. See IntervalStats.projected().
            It is included in summary(), plot_averages() and save_rokdoc_output(), and
            plot_logs_vs_burial_depth() marks where the trends cross this burial depth
        """
        if project_to_burial_depth is not None and not (isinstance(project_to_burial_depth, pint.Quantity)
                                                        and project_to_burial_depth.check('[length]')):
            raise ValueError('project_to_burial_depth must be a pint Quantity of length, not {}'.format(
                project_to_burial_depth))
        if isinstance(wells, dict):
            wells = list(wells.values())
        for _well in wells:
            if not isinstance(_well, Well):
                raise TypeError('wells must be core.well.Well objects, not {}'.format(type(_well)))
        if isinstance(wi_names, str):
            wi_names = [wi_names]
        n = len(wi_names)

        if working_dir is not None and not os.path.isdir(working_dir):
            print_info('The specified folder, where results should be saved, does not exist: {}'.format(
                working_dir), 'warning', logger)
            working_dir = None

        self.wells = wells
        self.intervals = intervals
        self.wi_names = wi_names
        self.cutoffs = [to_cutoffs(_c) for _c in _per_interval(cutoffs, n, 'cutoffs', (Cutoffs, str, dict))]
        # A single dict becomes one LogTable, so that a multi log LogTable only asks once, not once per interval
        if isinstance(log_table, dict) and not isinstance(log_table, LogTable):
            log_table = LogTable(log_table)
        self.log_tables = [(_lt if isinstance(_lt, LogTable) else LogTable(dict(_lt))).single_log()
                           for _lt in _per_interval(log_table, n, 'log_tables', (LogTable, dict))]
        self.suffixes = [_s or '' for _s in _per_interval(suffix, n, 'suffixes', (str,))]
        # The results, and the lines in the RokDoc output, of these could not be told apart
        _runs = list(zip(wi_names, self.suffixes))
        _repeated = sorted({_wi for _wi, _s in _runs if _runs.count((_wi, _s)) > 1})
        if len(_repeated) > 0:
            raise ValueError('The working intervals {} are repeated with the same suffix. Give each a different '
                             'suffix, e.g. suffix=["sand", "shale"]'.format(', '.join(_repeated)))
        self.working_dir = working_dir
        self.project_to_burial_depth = project_to_burial_depth

    def run(self) -> dict:
        """
        :return:
            dict
            {working interval name: IntervalStats}
            The key of a repeated interval also holds the suffix (IntervalStats.label), e.g. 'Sand F, sand'
        """
        results = {}
        for wi_name, cutoffs, log_table, suffix in zip(self.wi_names, self.cutoffs, self.log_tables, self.suffixes):
            print_info('Interval: {}. Cutoffs: {}'.format(wi_name, cutoffs), 'info', logger)
            stats = collect_interval_stats(self.wells, self.intervals, wi_name, log_table, cutoffs, suffix)
            stats.project_to_burial_depth = self.project_to_burial_depth
            results[wi_name if self.wi_names.count(wi_name) == 1 else stats.label] = stats
        return results

    def summary(self, results: dict) -> pd.DataFrame:
        return pd.concat([_r.summary() for _r in results.values()], ignore_index=True)

    def gardner(self, results: dict) -> pd.DataFrame:
        """
        Returns the Gardner coefficients of each interval and cutoff, see IntervalStats.gardner()
        """
        return pd.concat([_r.gardner() for _r in results.values()], ignore_index=True)

    def save_gardner(self, results: dict, file_name: str):
        """
        Writes the Gardner coefficients from gardner() to an excel file, which read_gardner() can read.
        An existing file is overwritten

        :param results:
            dict
            {working interval name: IntervalStats}, as returned by run()
        :param file_name:
            str
            full pathname of the excel file
        """
        self.gardner(results).to_excel(file_name, index=False)

    def well_style(self, well_name: str, index: int) -> tuple:
        """
        Returns the color and marker of the well, from its style when set, else from the default cycles
        """
        _well = next((_w for _w in self.wells if _w.name == well_name), None)
        # The project table gives the color of a well as its fill_color
        color = (_well.style.fill_color or _well.style.line_color) if _well is not None else None
        marker = _well.style.marker if _well is not None else None
        return color or xp.cnames[index % len(xp.cnames)], marker or xp.msymbols[index % len(xp.msymbols)]

    def log_template(self, log_name: str):
        """
        Returns the Template of the given log from the first well that has it
        """
        for _well in self.wells:
            if log_name in _well.get_log_names:
                return _well.get_log_curve(log_name).style
        return None

    def _set_xaxis(self, ax, log_name: str, units: str | None = None):
        template = self.log_template(log_name)
        label = log_name
        if template is not None:
            label = template.full_name or log_name
            if template.min is not None and template.max is not None:
                ax.set_xlim(template.min, template.max)
        if units:
            label += ' [{}]'.format(units)
        ax.set_xlabel(label)

    def save_summary(self, results: dict, file_name: str):
        """
        Writes the statistics from summary() to an excel file. An existing file is overwritten.
        Statistics of intervals without samples are left empty

        :param results:
            dict
            {working interval name: IntervalStats}, as returned by run()
        :param file_name:
            str
            full pathname of the excel file
        """
        self.summary(results).to_excel(file_name, index=False)

    def plot_logs_vs_depth(self, results: dict, file_name: str | None = 'logs_vs_depth.png'):
        """
        Plots the selected data of each log versus depth from the top of the interval, one row per interval
        """
        log_names = self.log_tables[0].log_names
        fig, axes = plt.subplots(nrows=len(results), ncols=len(log_names), squeeze=False,
                                 figsize=(2 * len(log_names), 3 * len(results)))
        all_wells = [_w.name for _w in self.wells]
        for j, stats in enumerate(results.values()):
            for i, log_name in enumerate(stats.log_table.log_names):
                ax = axes[j][i]
                units = None
                for well_name, data in stats.per_well.items():
                    if log_name not in data:
                        continue
                    units = str(data[log_name].units)
                    color, _ = self.well_style(well_name, all_wells.index(well_name))
                    x, y = break_at_gaps(data[log_name].magnitude, stats.depth_from_top[well_name].magnitude)
                    ax.plot(x, y, c=color, label=well_name)
                    single = isolated_samples(x, y)
                    ax.plot(x[single], y[single], ls='none', marker='.', ms=4, c=color)
                self._set_xaxis(ax, log_name, units)
                ax.set_ylim(ax.get_ylim()[::-1])
            axes[j][0].set_ylabel('Depth from top of {} [m]'.format(stats.label))
        handles, labels = axes[0][-1].get_legend_handles_labels()
        if len(handles) > 0:
            axes[0][-1].legend(handles, labels, prop={'size': 10})
        fig.tight_layout()
        self._save(fig, file_name)
        return fig

    def plot_averages(self, results: dict):
        """
        Plots the mean and standard deviation of each log, per well and for all wells, one figure per log type
        :return:
            dict
            {log type: Figure}
        """
        figs = {}
        all_wells = [_w.name for _w in self.wells]
        log_types = list(self.log_tables[0].keys())
        for log_type in log_types:
            fig, ax = plt.subplots(figsize=(9, 8))
            units = None
            plotted_wells = []
            for j, stats in enumerate(results.values()):
                if log_type not in stats.log_table:
                    continue
                log_name = stats.log_table[log_type]
                for well_name, data in stats.per_well.items():
                    if log_name not in data or len(data[log_name]) == 0:
                        continue
                    units = str(data[log_name].units)
                    color, marker = self.well_style(well_name, all_wells.index(well_name))
                    mn, std = np.nanmean(data[log_name].magnitude), np.nanstd(data[log_name].magnitude)
                    ax.errorbar(mn, j, xerr=std, fmt='none', capsize=10, capthick=1, elinewidth=1, ecolor=color)
                    ax.scatter(mn, j, marker=marker, c=color, s=90,
                               label=well_name if well_name not in plotted_wells else None)
                    plotted_wells.append(well_name)
                combined = stats.combined()
                if log_name in combined and len(combined[log_name]) > 0:
                    mn, std = np.nanmean(combined[log_name].magnitude), np.nanstd(combined[log_name].magnitude)
                    ax.errorbar(mn, j, xerr=std, fmt='none', capsize=20, capthick=3, elinewidth=3, ecolor='pink')
                    ax.scatter(mn, j, marker='*', s=360, c='pink', label='All' if j == 0 else None)
                projected = stats.projected()
                if log_name in projected:
                    mn, std = np.nanmean(projected[log_name].magnitude), np.nanstd(projected[log_name].magnitude)
                    ax.errorbar(mn, j, xerr=std, fmt='none', capsize=20, capthick=2, elinewidth=2, ecolor='skyblue')
                    ax.scatter(mn, j, marker='*', s=240, c='skyblue', edgecolors='k',
                               label=stats.projected_label if stats.projected_label not in plotted_wells else None)
                    plotted_wells.append(stats.projected_label)
            ax.grid(True)
            ax.legend(prop={'size': 10})
            ax.set_yticks(range(len(results)))
            ax.set_yticklabels([_r.label for _r in results.values()])
            self._set_xaxis(ax, self.log_tables[0][log_type], units)
            fig.tight_layout()
            self._save(fig, '{}.png'.format(log_type))
            figs[log_type] = fig
        return figs

    def plot_logs_vs_burial_depth(self, results: dict, file_name: str | None = 'logs_vs_burial_depth.png',
                                  max_intervals: int = 4) -> list:
        """
        QC plot of how much the statistics of each interval are affected by its burial depth varying between the
        wells. Plots each log versus burial depth (TVD below the sea floor), one row per interval, with:
            - the selected samples, the mean and the standard deviation of each well, colored by well
            - the mean of all wells together
            - a linear trend through the samples of all wells, its slope and its R2
            - the standard deviation of all wells together, with and without the trend. When these differ, part of
              the spread of the combined statistics follows depth
            - the number of wells behind the trend. With one well it says nothing about the differences between wells
            - with project_to_burial_depth, thin dashed lines where the trend crosses that burial depth

        The burial depth needs a TVD log, and the kelly bushing and water depth from the project table. Wells lacking
        any of these can't be included, they are listed in the title of the figure

        :param results:
            dict
            {working interval name: IntervalStats}, as returned by run()
        :param file_name:
            str
            Name of the saved file. When there is more than one figure, they are numbered, e.g.
            logs_vs_burial_depth_1.png, logs_vs_burial_depth_2.png
        :param max_intervals:
            int
            The maximum number of intervals in one figure
        :return:
            list of Figure
            Also when there is only one figure
        """
        lacking = _lacking_burial_depth(results)
        if len(lacking) > 0:
            print_info('Wells lacking a TVD log, kelly bushing or water depth are not included in the plot versus '
                       'burial depth: {}'.format(', '.join(lacking)), 'warning', logger)

        items = list(results.items())
        parts = [dict(items[_i:_i + max_intervals]) for _i in range(0, len(items), max_intervals)]
        figs = []
        for i, part in enumerate(parts):
            _file_name = file_name
            if file_name is not None and len(parts) > 1:
                _root, _extension = os.path.splitext(file_name)
                _file_name = '{}_{}{}'.format(_root, i + 1, _extension)
            figs.append(self._plot_logs_vs_burial_depth_figure(part, _file_name))
        return figs

    def _plot_logs_vs_burial_depth_figure(self, results: dict, file_name: str | None):
        log_names = self.log_tables[0].log_names
        fig, axes = plt.subplots(nrows=len(results), ncols=len(log_names), squeeze=False, sharey='row',
                                 figsize=(3 * len(log_names), 3.5 * len(results) + 0.5), layout='constrained')
        all_wells = [_w.name for _w in self.wells]
        legend_items = {}
        for j, stats in enumerate(results.values()):
            for i, log_name in enumerate(stats.log_table.log_names):
                ax = axes[j][i]
                units = None
                for well_name, data in stats.per_well.items():
                    if well_name not in stats.burial_depth or not _log_in_well(data, log_name):
                        continue
                    units = str(data[log_name].units)
                    x, y = data[log_name].magnitude, stats.burial_depth[well_name].magnitude
                    valid = np.isfinite(x) & np.isfinite(y)
                    if not np.any(valid):
                        continue
                    color, marker = self.well_style(well_name, all_wells.index(well_name))
                    ax.scatter(x[valid], y[valid], s=4, alpha=0.3, color=color, edgecolors='none', rasterized=True)
                    legend_items[well_name] = ax.errorbar(
                        np.mean(x[valid]), np.mean(y[valid]), xerr=np.std(x[valid]), marker=marker, ms=8, color=color,
                        mec='k', ecolor=color, capsize=4, ls='none', zorder=4)

                values, depth = stats.samples_with_burial_depth(log_name)
                if values is not None:
                    x = values.magnitude
                    valid = np.isfinite(x) & np.isfinite(depth)
                    if np.any(valid):
                        legend_items['All wells with burial depth'] = ax.scatter(
                            np.mean(x[valid]), np.mean(depth[valid]), marker='*', s=220, c='pink', edgecolors='k',
                            zorder=5)
                    trend = linear_depth_trend(x, depth)
                    if trend is not None:
                        y = np.array([np.min(depth[valid]), np.max(depth[valid])])
                        if stats.project_to_burial_depth is not None:
                            # Mark where the trend, extended if necessary, crosses the burial depth
                            target = stats.project_to_burial_depth.to('m').magnitude
                            y = np.array([min(y[0], target), max(y[1], target)])
                            ax.axvline(trend['slope'] * target + trend['intercept'], color='k', ls='--', lw=0.7,
                                       zorder=3)
                            legend_items[stats.projected_label] = ax.axhline(target, color='k', ls='--', lw=0.7,
                                                                             zorder=3)
                            ax.text(0.98, target, '{:g} m'.format(target), transform=ax.get_yaxis_transform(),
                                    ha='right', va='bottom', fontsize=7, zorder=6)
                        legend_items['Linear trend'] = ax.plot(trend['slope'] * y + trend['intercept'], y, 'k-', lw=1.5,
                                                               zorder=3)[0]
                        # With one well, the trend only shows the variation within that well
                        n_wells = len([_w for _w, _d in stats.per_well.items()
                                       if _w in stats.burial_depth and _log_in_well(_d, log_name)])
                        ax.set_title(
                            '{} well{}, {:+.3g} {} per 100 m, R2 = {:.2f}\nStd {:.3g}, after de-trend {:.3g}'.format(
                                n_wells, '' if n_wells == 1 else 's', 100. * trend['slope'], units, trend['r2'],
                                trend['std'], trend['std_detrended']),
                            fontsize=7, loc='left')
                self._set_xaxis(ax, log_name, units)
                ax.grid(True)
            axes[j][0].set_ylabel('Burial depth of {} [m]'.format(stats.label))
            # The y-axes of a row are shared, so this applies to all of them
            axes[j][0].invert_yaxis()

        if len(legend_items) > 0:
            fig.legend(list(legend_items.values()), list(legend_items.keys()), loc='outside lower center',
                       ncols=len(legend_items), prop={'size': 9})
        lacking = _lacking_burial_depth(results)
        if len(lacking) > 0:
            fig.suptitle('Not included, lacking a TVD log, kelly bushing or water depth: {}'.format(
                ', '.join(lacking)), fontsize=10)
        self._save(fig, file_name)
        return fig

    def plot_gardner(self, results: dict, file_name: str | None = 'gardner.png', n_columns: int = 3):
        """
        Plots density versus P velocity, one panel per interval, with the published equation (rho = 0.31 * vp ** 0.25)
        for reference, and:
            - the samples, the calibrated Gardner equation, the mean and the standard deviation of each well, in the
              color and marker of the well
            - the calibrated Gardner equation and the mean of all wells together

        :param results:
            dict
            {working interval name: IntervalStats}, as returned by run()
        :param file_name:
            str
            Name of the saved file
        :param n_columns:
            int
            The maximum number of panels per row
        :return:
            Figure
        """
        fig, axes = self._panels(len(results), n_columns)
        all_wells = [_w.name for _w in self.wells]
        legend_items = {}
        for ax, stats in zip(axes.flat, results.values()):
            samples = stats.vp_and_rho()
            for well_name, (vp, rho) in samples.items():
                valid = _valid_vp_and_rho(vp, rho)
                if not np.any(valid):
                    continue
                vp_range = np.linspace(np.min(vp[valid]), np.max(vp[valid]), 50)
                trend = fit_gardner(vp, rho)
                if well_name == 'All':
                    legend_items['All wells'] = _plot_mean_of_all_wells(ax, vp[valid], rho[valid])
                    if trend is not None:
                        legend_items['Calibrated, all wells'] = ax.plot(
                            vp_range, trend['a'] * vp_range ** trend['b'], 'k-', lw=2, zorder=4)[0]
                        legend_items['Published, a = {}, b = {}'.format(gardner_a, gardner_b)] = ax.plot(
                            vp_range, gardner_a * vp_range ** gardner_b, 'k--', lw=1, zorder=3)[0]
                    continue
                color, marker = self.well_style(well_name, all_wells.index(well_name))
                legend_items[well_name] = _plot_samples_of_well(ax, vp[valid], rho[valid], color, marker)
                if trend is not None:
                    ax.plot(vp_range, trend['a'] * vp_range ** trend['b'], '-', c=color, lw=1, zorder=3)
            trend = fit_gardner(*samples['All']) if 'All' in samples else None
            ax.set_title('{}\n{}'.format(
                stats.label, 'No fit' if trend is None else 'All wells: a = {:.3f}, b = {:.3f}, R2 = {:.2f}'.format(
                    trend['a'], trend['b'], trend['r2'])), fontsize=9, loc='left')
            ax.grid(True)
        self._finish_panels(fig, axes, len(results), 'Vp [m/s]', 'Density [g/cm3]', legend_items, file_name)
        return fig

    def plot_elastics(self, results: dict, file_name: str | None = 'elastics.png', n_columns: int = 3):
        """
        Plots Vp/Vs versus acoustic impedance (Vp * Rho), one panel per interval, with the samples, the mean and the
        standard deviation of each well, in the color and marker of the well, and the mean of all wells together.
        Only wells with P velocity, S velocity and density are included

        :param results:
            dict
            {working interval name: IntervalStats}, as returned by run()
        :param file_name:
            str
            Name of the saved file
        :param n_columns:
            int
            The maximum number of panels per row
        :return:
            Figure
        """
        lacking = [_s.label for _s in results.values() if
                   any(_x not in _s.log_table for _x in ['P velocity', 'S velocity', 'Density'])]
        if len(lacking) > 0:
            print_info('The log table lacks P velocity, S velocity or density, so there are no elastics to plot for: '
                       '{}'.format(', '.join(lacking)), 'warning', logger)

        fig, axes = self._panels(len(results), n_columns)
        all_wells = [_w.name for _w in self.wells]
        legend_items = {}
        for ax, stats in zip(axes.flat, results.values()):
            for well_name, (ai, vpvs) in stats.ai_and_vpvs().items():
                valid = np.isfinite(ai) & np.isfinite(vpvs) & (ai > 0.) & (vpvs > 0.)
                if not np.any(valid):
                    continue
                if well_name == 'All':
                    legend_items['All wells'] = _plot_mean_of_all_wells(ax, ai[valid], vpvs[valid])
                    continue
                color, marker = self.well_style(well_name, all_wells.index(well_name))
                legend_items[well_name] = _plot_samples_of_well(ax, ai[valid], vpvs[valid], color, marker)
            ax.set_title(stats.label, fontsize=9, loc='left')
            ax.grid(True)
        self._finish_panels(fig, axes, len(results), 'Acoustic impedance [km/s*g/cm3]', 'Vp/Vs', legend_items, file_name)
        return fig

    @staticmethod
    def _panels(n_panels: int, n_columns: int) -> tuple:
        """
        Returns the figure and axes of a grid of panels with shared axes, with at most n_columns panels per row
        """
        n_columns = min(n_columns, n_panels)
        n_rows = int(np.ceil(n_panels / n_columns))
        return plt.subplots(nrows=n_rows, ncols=n_columns, squeeze=False, sharex=True, sharey=True,
                            figsize=(5 * n_columns, 4 * n_rows + 0.5), layout='constrained')

    def _finish_panels(self, fig, axes, n_panels: int, x_label: str, y_label: str, legend_items: dict,
                       file_name: str | None):
        """
        Hides the unused panels, adds the axis labels and the legend of a figure from _panels(), and saves it
        """
        for ax in axes.flat[n_panels:]:
            ax.set_visible(False)
        for ax in axes[:, 0]:
            ax.set_ylabel(y_label)
        # The lowest panel of each column, which is not in the last row below a hidden panel
        for ax in axes.flat[n_panels - axes.shape[1]:n_panels]:
            ax.set_xlabel(x_label)
            ax.xaxis.set_tick_params(labelbottom=True)
        if len(legend_items) > 0:
            handles = list(legend_items.values())
            fig.legend(handles, list(legend_items.keys()), loc='outside lower center', ncols=len(handles),
                       prop={'size': 9})
        self._save(fig, file_name)

    def save_rokdoc_output(self, results: dict, file_name: str):
        """
        Writes the averages of each interval, for all wells and for each well, to a RokDoc compatible
        Sums and Averages excel file. Averages of intervals without samples are written as -999.25
        """
        for stats in results.values():
            missing = [_lt for _lt in rokdoc_log_types if _lt not in stats.log_table]
            if len(missing) > 0:
                print_info('Logs of type {} are lacking for storing {} as a RokDoc Sums and Averages file'.format(
                    ', '.join(missing), stats.wi_name), 'warning', logger)
                continue
            suffix = '_{}'.format(stats.suffix) if stats.suffix else ''
            sources = [(None, stats.combined())] + list(stats.per_well.items())
            for well_name, data in sources:
                # write_rokdoc_sums_and_averages expects arrays without units, for all logs in the log table
                _arrays = {_log: data[_log].magnitude if _log in data else np.array([np.nan])
                           for _log in stats.log_table.log_names}
                write_rokdoc_sums_and_averages(file_name, _arrays, stats.wi_name, stats.log_table,
                                               str(stats.cutoffs), suffix, well_name=well_name)
            projected = stats.projected()
            if len(projected) > 0:
                # Like the line of all wells, but its name tells the burial depth
                _arrays = {_log: projected[_log].magnitude if _log in projected else np.array([np.nan])
                           for _log in stats.log_table.log_names}
                write_rokdoc_sums_and_averages(
                    file_name, _arrays, stats.wi_name, stats.log_table, str(stats.cutoffs),
                    '{}_projected_{:g}m'.format(suffix, stats.project_to_burial_depth.to('m').magnitude))

    def _save(self, fig, file_name: str | None):
        if self.working_dir is not None and file_name is not None:
            fig.savefig(os.path.join(self.working_dir, file_name), dpi=300)


def write_rokdoc_sums_and_averages(rokdoc_output, results, wi_name, log_table, cutoffs_str, suffix, well_name=None):
    """
    Writes one line of averages to a RokDoc compatible Sums and Averages excel file.
    Moved here from the old calc_stats.py (save_rokdoc_output())

    :param rokdoc_output:
        str
        full pathname of the excel file. It is created if it does not exist, otherwise the line is appended
    :param results:
        dict
        arrays without units, with the log names in the log table as keys
    :param wi_name:
        str
        name of the working interval
    :param log_table:
        LogTable or dict
        must contain the log types 'P velocity', 'S velocity', 'Density', 'Porosity' and 'Volume'
    :param cutoffs_str:
        str
        description of the cutoffs used
    :param suffix:
        str
        added to the name of the line
    :param well_name:
        str
        If None, the line holds the averages of all wells
    """
    if well_name is not None:
        well_name = str(well_name)
        name = '{} {}{}'.format(well_name, wi_name, suffix)
    else:
        well_name = 'NONE'
        name = '{}{}'.format(wi_name, suffix)
    if not isinstance(log_table, LogTable):
        log_table = LogTable(log_table)
    log_table = log_table.single_log()
    log_table_str = ''
    for key in log_table:
        log_table_str += '{}: {}, '.format(key, log_table[key])
    log_table_str = log_table_str.rstrip(', ')

    # To calculate correlation coefficients, the results for P-, and S- velocity, and Density, must
    # be equal in length.
    # Create a naive fix by cutting the data to the shortest
    min_len = min([len(results[log_table['P velocity'].lower()]),
                   len(results[log_table['S velocity'].lower()]),
                   len(results[log_table['Density'].lower()])
                   ])
    cc_p_s = nan_corrcoef(results[log_table['P velocity'].lower()][:min_len],
                          results[log_table['S velocity'].lower()][:min_len])[0, 1]
    cc_p_d = nan_corrcoef(results[log_table['P velocity'].lower()][:min_len],
                          results[log_table['Density'].lower()][:min_len])[0, 1]
    cc_s_d = nan_corrcoef(results[log_table['S velocity'].lower()][:min_len],
                          results[log_table['Density'].lower()][:min_len])[0, 1]

    if rokdoc_output is not None:
        uio.write_sums_and_averages(rokdoc_output,
                                    [
                                        name,
                                        well_name,
                                        'MD',
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        np.nanmean(results[log_table['P velocity'].lower()]),
                                        np.nanmean(results[log_table['S velocity'].lower()]),
                                        np.nanmean(results[log_table['Density'].lower()]),
                                        np.nanmedian(results[log_table['P velocity'].lower()]),
                                        np.nanmedian(results[log_table['S velocity'].lower()]),
                                        np.nanmedian(results[log_table['Density'].lower()]),
                                        np.nanmean(results[log_table['P velocity'].lower()]),
                                        # this should be a mode value, but uncertain what it means
                                        np.nanmean(results[log_table['S velocity'].lower()]),
                                        # this should be a mode value, but uncertain what it means
                                        np.nanmean(results[log_table['Density'].lower()]),
                                        # this should be a mode value, but uncertain what it means
                                        'NONE',
                                        np.nanmean(results[log_table['Porosity'].lower()]),
                                        np.nanstd(results[log_table['Porosity'].lower()]),
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        np.nanstd(results[log_table['P velocity'].lower()]),
                                        np.nanstd(results[log_table['S velocity'].lower()]),
                                        np.nanstd(results[log_table['Density'].lower()]),
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        cc_p_s,
                                        cc_p_d,
                                        cc_s_d,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        np.nanmean(results[log_table['Shear modulus'].lower()]) \
                                            if ('Shear modulus' in list(log_table.keys())) else -999.25,
                                        np.nanmean(results[log_table['Bulk modulus'].lower()]) \
                                            if ('Bulk modulus' in list(log_table.keys())) else -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        -999.25,
                                        np.nanmean(results[log_table['Volume'].lower()]),
                                        np.nanstd(results[log_table['Volume'].lower()]),
                                        'None',
                                        0.0,
                                        cutoffs_str,
                                        log_table_str,
                                        datetime.now()
                                    ]
                                    )
