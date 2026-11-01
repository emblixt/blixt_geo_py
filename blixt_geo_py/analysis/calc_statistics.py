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
                             cutoffs='Volume<0.5[], Porosity>0.1[]',
                             log_table={'P velocity': 'vp_dry', 'Porosity': 'phie', 'Volume': 'vcl'})
    results = stats.run()
    print(results['Sand E'].summary())
    stats.save_summary(results, 'summary.xlsx')
    stats.plot_logs_vs_depth(results)
    stats.plot_averages(results)
    stats.plot_logs_vs_burial_depth(results)
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
        for _param, (_operator, _limit) in cutoffs.items():
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
            'r2': 1. - (std_detrended / std) ** 2 if std > 0. else 0.,
            'std': std, 'std_detrended': std_detrended, 'n': int(np.sum(valid))}


def _log_in_well(data: dict, log_name: str) -> bool:
    return log_name in data and len(data[log_name]) > 0


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

    def summary(self) -> pd.DataFrame:
        """
        Returns the number of samples, mean, median, standard deviation, P10 and P90 of each log,
        per well and for all wells together ('All')
        """
        rows = []
        sources = list(self.per_well.items()) + [('All', self.combined())]
        for _well_name, _data in sources:
            for _log_type, _log in self.log_table.items():
                if _log not in _data:
                    continue
                _values = _data[_log].magnitude
                rows.append({
                    'interval': self.wi_name, 'well': _well_name, 'log type': _log_type, 'log': _log,
                    'units': str(_data[_log].units), 'n': int(np.sum(~np.isnan(_values))),
                    'mean': np.nanmean(_values), 'median': np.nanmedian(_values), 'std': np.nanstd(_values),
                    'p10': np.nanpercentile(_values, 10), 'p90': np.nanpercentile(_values, 90)
                })
        return pd.DataFrame(rows)


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
                 cutoffs: Cutoffs | str | dict | list | None,
                 log_table: LogTable | dict | list,
                 suffix: str | list = '',
                 working_dir: str | None = None):
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
        :param cutoffs:
            Cutoffs, str (e.g. "Volume<0.5[], Porosity>0.1[]"), dict (e.g. {'Volume': ['<', 0.5]}) or None
            If a single value, it is used in all working intervals
            If it is a list, it must have the same length as wi_names
        :param log_table:
            LogTable or dict of {log type: log name}, or a list of these, one per working interval
            The P velocity, S velocity, Density, Porosity and Volume logs are needed for the RokDoc output
        :param suffix:
            str or list of strings
            Tags the results of each working interval
        :param working_dir:
            str
            Folder where the figures are saved
        """
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
        self.log_tables = [_lt if isinstance(_lt, LogTable) else LogTable(dict(_lt))
                           for _lt in _per_interval(log_table, n, 'log_tables', (LogTable, dict))]
        self.suffixes = [_s or '' for _s in _per_interval(suffix, n, 'suffixes', (str,))]
        self.working_dir = working_dir

    def run(self) -> dict:
        """
        :return:
            dict
            {working interval name: IntervalStats}
        """
        results = {}
        for wi_name, cutoffs, log_table, suffix in zip(self.wi_names, self.cutoffs, self.log_tables, self.suffixes):
            print_info('Interval: {}. Cutoffs: {}'.format(wi_name, cutoffs), 'info', logger)
            results[wi_name] = collect_interval_stats(self.wells, self.intervals, wi_name, log_table, cutoffs, suffix)
        return results

    def summary(self, results: dict) -> pd.DataFrame:
        return pd.concat([_r.summary() for _r in results.values()], ignore_index=True)

    def well_style(self, well_name: str, index: int) -> tuple:
        """
        Returns the color and marker of the well, from its style when set, else from the default cycles
        """
        _well = next((_w for _w in self.wells if _w.name == well_name), None)
        color = _well.style.line_color if _well is not None else None
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
            ax.grid(True)
            ax.legend(prop={'size': 10})
            ax.set_yticks(range(len(results)))
            ax.set_yticklabels([_r.label for _r in results.values()])
            self._set_xaxis(ax, self.log_tables[0][log_type], units)
            fig.tight_layout()
            self._save(fig, '{}.png'.format(log_type))
            figs[log_type] = fig
        return figs

    def plot_logs_vs_burial_depth(self, results: dict, file_name: str | None = 'logs_vs_burial_depth.png'):
        """
        QC plot of how much the statistics of each interval are affected by its burial depth varying between the
        wells. Plots each log versus burial depth (TVD below the sea floor), one row per interval, with:
            - the selected samples, the mean and the standard deviation of each well, colored by well
            - the mean of all wells together
            - a linear trend through the samples of all wells, its slope and its R2
            - the standard deviation of all wells together, with and without the trend. When these differ, part of
              the spread of the combined statistics follows depth
            - the number of wells behind the trend. With one well it says nothing about the differences between wells

        The burial depth needs a TVD log, and the kelly bushing and water depth from the project table. Wells lacking
        any of these can't be included, they are listed in the title of the figure
        :return:
            Figure
        """
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
                        legend_items['Linear trend'] = ax.plot(trend['slope'] * y + trend['intercept'], y, 'k-', lw=1.5,
                                                               zorder=3)[0]
                        # With one well, the trend only shows the variation within that well
                        n_wells = len([_w for _w, _d in stats.per_well.items()
                                       if _w in stats.burial_depth and _log_in_well(_d, log_name)])
                        ax.set_title(
                            '{} well{}, {:+.3g} {} per 100 m, R2 = {:.2f}\nStd {:.3g}, without trend {:.3g}'.format(
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
        lacking = [_w for _w in all_wells
                   if any(_w in _r.per_well and _w not in _r.burial_depth for _r in results.values())]
        if len(lacking) > 0:
            print_info('Wells lacking a TVD log, kelly bushing or water depth are not included in the plot versus '
                       'burial depth: {}'.format(', '.join(lacking)), 'warning', logger)
            fig.suptitle('Not included, lacking a TVD log, kelly bushing or water depth: {}'.format(
                ', '.join(lacking)), fontsize=10)
        self._save(fig, file_name)
        return fig

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
