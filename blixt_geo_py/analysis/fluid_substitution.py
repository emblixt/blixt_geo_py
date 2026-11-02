"""
Outline:
    This is to be a new home for fluid substitution, but with all the "new" functions and methods that allows
    pint Quantities

    It should have two main functionalities:
    1. One 'advanced' function
        Copy and rewrite the run_fluid_sub() from rp_core.py (removed, see commit 35b133f or earlier),
        AND run_fluid_substitution.py,
        OR, at least use them as inspiration

    2. One 'naiv' method that is interactive and uses bokeh as front-end
           InteractiveFluidSub, which works on the selected LithoFluid in a LithoFluidsTable
"""
import logging
import os
from collections.abc import Callable
from copy import deepcopy
from math import isfinite
from pathlib import Path

from bokeh.models import Button, ColumnDataSource, Dialog, Div, Spinner
from bokeh.plotting import column, row
import pint

from blixt_geo_py import Q_
from blixt_geo_py.core.well import Well
from blixt_geo_py.utils.utils import isnan, print_info
from blixt_geo_py.core.core import Intervals, LithoFluid, LithoFluids, LogTable, Cutoffs
from blixt_geo_py.rp.rp_core import gassmann_vel
from blixt_geo_py.core.fluids_and_minerals import load_substitution_cases

logger = logging.getLogger(__name__)

def run_fluid_substitution(
        wells: dict,
        project_table: str | Path,
        log_table: LogTable,
        lithology_cutoffs: Cutoffs,
        working_intervals: Intervals,
        pvt_table: dict | None = None,
        save_result_folder: Path | str | None = None,
        result_file_postfix: str | None = 'FS',
        verbose: bool = False
):

    """

    This 'advanced' option takes the fluid, and mineral, properties and their respective mixtures, from the
    'project table' Excel file.
    It describes a Gassmann fluid substitution in multiple intervals for multiple wells, where the fluid properties
    are given in the sheet "Fluids" of the 'project table' Excel file, and the initial and final mixtures
    (for each well and each interval) of the fluids are given in the "Fluid mixtures" sheet:

    -The column 'Use' of the "Fluid mixtures" sheet is either 'Yes' or 'No'. If not 'Yes', the given well and interval
     combination is ignored.

    -The column 'Substitution order' of the "Fluid mixtures" sheet is either 'Initial' or 'Final'. Which describes the
     substitution order that goes from initial to final.

    -The column 'Well name' of the "Fluid mixtures" sheet contains the name of the well for which the fluid substitution
    is to be done

    -The column 'Interval name' of the "Fluid mixtures" sheet contains the name of the interval (specified elsewhere as
    top and bottom measured depth) for which the fluid substitution is to be done

    -The 'Tag' column makes it possible to run different fluid sub. scenarios in the same well & interval, e.g.
    'fs_oil_08' and 'fs_gas_09'

    A *fluid substitution case* is defined by a unique combination of Well name, Interval name and Tag

    -The column 'Fluid name' of the "Fluid mixtures" sheet determines which of the fluids in the "Fluids" sheet to use

    -The "Fluid type" column determines which fluid ('Brine', 'Oil' or 'Gas') the Batzle and Wang method should calculate.
    Or it can be 'User specified', which means that no calculation is needed - it just takes the given Bulk, Shear moduli
    and density.

    -The column "Volume fraction" of the "Fluid mixtures" sheet, which determines the fraction of each fluid type,
    is either the name of a specific well log curve (e.g. SW = water saturation), a constant (e.g. 0,2),
    or "complement" (meaning that it occupies the rest of the pore volume. The total pore volume is of course 1.

    For the "Fluids" sheet of the 'project table' Excel file, we have the following columns:

    -'Name': a unique name of this specific fluid

    -'Bulk moduli', 'Shear moduli' and 'Density' can be given as fixed values in these columns when the column
      'Calculation method' is set to 'User specified'

   -'Calculation method' is either 'User specified' or 'Batzle and Wang'

   - The other columns are parameters that are used by the Batzle and Wang calculation

    :param wells:
        dict
        Dictionary with well name: Well object as key: value pairs
    :param project_table:
        str | Path
        file path to the project table .xlsx file that contains the Fluid and Mineral specifications
    :param log_table:
        LogTable
        LogTable object contain the mapping between a log type (e.g. 'P velocity') and a specific log (e.g. 'vp_oil')
    :param lithology_cutoffs:
        Cutoffs
        The Cutoffs object contains a list of cut-off rules which are used to define the lithology the
        fluid substitution should be applied to (that is, preferably sands)

        Some mineral properties are calculated using cutoffs too (e.g. Shale), but those cutoffs are specified
        in the project_table.
        Because of these mineral-specific cutoffs, it is important to NOT apply the lithology_cutoffs of the fluid-substitution
        before we start with the calculations.
    :param working_intervals:
        Intervals
        Holds the information about the working intervals that are defined for the wells
    :param pvt_table:
        dict
        Dictionary that contains pressure, density and bulk modulus values from typically a PVT simulation.
        It can be used to calculate the elastic properties as a function of pressure for fluids (e.g. gas condensates)
        which can't be modelled accurately from Batzle & Wang
        E.G.
            pvt_table = dict(
                pressure = Q_([10., 15., 20., 25., 30., 35., 40., 45., 50.], 'MPa'),
                rho = Q_([0.12, 0.18, 0.25, 0.31, 0.38, 0.45, 0.52, 0.58, 0.64], 'g/cc'),
                k = Q_([0.020, 0.035, 0.055, 0.080, 0.110, 0.145, 0.185, 0.230, 0.28], 'GPa')
            )
    :param save_result_folder:
        Path | str | None
        If None, the results are not saved
        Else each well is saved as a las file in the specified folder, with the name:
            <WELL NAME>_<result_file_postfix>.las
    :param result_file_postfix:
        str | None
        default 'FS'
        Postfix added to the resulting las file,
    :param verbose:
    :return:
    """
    log_table = log_table.single_log(['P velocity', 'S velocity', 'Density', 'Porosity'])

    # Load all fluid substitution cases:
    fluid_subst_cases = load_substitution_cases(project_table)

    # Load all mineral mixtures
    mineral_subst_cases = load_substitution_cases(project_table, from_fluid_mixture=False)

    last_well = None
    last_mod_history = ''
    # Iterate over all fluid substitution cases:
    for fsc in fluid_subst_cases:
        print('\n-----------------------------------------------------------------------------' )
        mod_history = f'\nRunning fluid substitution in well {fsc.well}, in interval {fsc.interval}, with tag={fsc.tag}\n'
        if verbose:
            print(mod_history)

        # Check if this well | interval pair is among the mineral cases
        msc = None
        for _msc in mineral_subst_cases:
            if _msc.well == fsc.well and _msc.interval == fsc.interval:
                msc = _msc
        if msc is None:
            err_txt = f'There is no mineral case listed in {os.path.basename(project_table)} that matches well {fsc.well} and interval {fsc.interval}'
            print_info(err_txt, 'error', logger, raiser='IOError')

        # Check if the well exist
        if fsc.well.upper() not in list(wells.keys()):
            err_txt = f'There is no well {fsc.well} among the input wells'
            print_info(err_txt, 'error', logger, raiser='IOError')

        # Extract current well from the input
        well = wells[fsc.well.upper()]

        # For the first iteration:
        if last_well is None:
            last_well = well

        # Identify if we have met a new well in fsc
        if last_well.name != fsc.well.upper():
            new_well = True
            # Save the last well if we have asked for it
            if save_result_folder is not None:
                _tag = '' if result_file_postfix is None else '_{}'.format(result_file_postfix)
                _file_name = os.path.join(save_result_folder, '{}{}.las'.format(last_well.name, _tag))
                print('Saving to {}'.format(_file_name))
                last_well.header.modification_history += last_mod_history
                last_well.write_las(_file_name)
            last_mod_history = ''
        else:
            new_well = False

        # Prepare the well to be used as input for the fluid and mineral elastics calculation
        # The dict method harmonizes the logs in this well.
        well_dict = well.dict()

        # Add the necessary keys needed to calculate the mineral properties
        for _new_key, _log_type in zip(['vp', 'vs', 'rho'], ['P velocity', 'S velocity', 'Density']):
            well_dict[_new_key] = well_dict[log_table[_log_type]]

        # Get the cut-off rule that corresponds to this specific well and interval pair
        interval_rule = working_intervals.get_cutoff_rule(fsc.interval, fsc.well)

        # Make a copy of the lithology_cutoffs so that you can modify this local version of it
        local_cutoffs = deepcopy(lithology_cutoffs)

        # Add the interval_rule to these cutoffs
        local_cutoffs.append([interval_rule])
        # And calculate the mask. This mask identifies the lithology defined by the input lithology_cutoffs (hopefully sands)
        # within this interval
        local_mask = local_cutoffs.create_mask(well_dict)

        # Calculate the interval mask given the interval rules and input data
        interval_cutoffs = Cutoffs([interval_rule])
        interval_mask = interval_cutoffs.create_mask(well_dict)

        # In the unit-ignorant version of the dictionary, used by the mineral elastic calculation,
        # apply the interval mask
        # (Remember that we cant apply the input lithology_cutoffs, as we then typically only keep sands and remove the shale)
        well_dict_wo_units = {_key: _value.magnitude[interval_mask] if isinstance(_value, Q_) else _value[interval_mask] for _key, _value in well_dict.items()}

        # Print the log parameters and their length before and after applying the mask
        if verbose:
            print(list(well_dict_wo_units.keys()))
        mod_history += ' -Interval rule: {}\n'.format(interval_rule)
        for _key in list(well_dict_wo_units.keys()):
            if _key == 'md':
                mod_history += ' -{}: length before & after mask; {} & {}\n'.format(_key,
                    len(well_dict[_key]), len(well_dict_wo_units[_key]))
                mod_history += ' -MD data now covers: {} to  {}\n'.format(well_dict_wo_units[_key][0], well_dict_wo_units[_key][-1])

        # Extract the burial depth to this specific substitution case
        bd = working_intervals.get_interval(fsc.interval, fsc.well).mid

        # Calculate the fluid elastic properties ('well_dict_wo_units' is not used in this calculation)
        mod_history += fsc.calc_elastics(well_dict_wo_units, bd, pvt_table=pvt_table, verbose=verbose)

        # Calculate the mineral elastic properties ('bd' is not used in this calculation)
        mod_history += msc.calc_elastics(well_dict_wo_units, bd, verbose=verbose)

        # Now that we have calculated the fluid and mineral elastics, we can apply the initial cutoff on these
        # results.
        # Because we previously masked out everything outside our interval, we now identify the lithology within
        # this interval that matches the initial cutoff (hopefully sands)
        # To do that, we first create a data set that just contain the data needed by the cutoff rule
        _data = {_param.lower(): well_dict_wo_units[_param.lower()] for _param in lithology_cutoffs.cutoff_params}
        # Then we calculate the mask
        lithology_mask = lithology_cutoffs.create_mask(_data)


        # check consistency of input data
        # if verbose:
        if False:
            print('INPUT:')
            print('  Vp: ', type(well_dict['vp']), len(well_dict['vp'][local_mask]))
            print('  Vs: ', type(well_dict['vs']), len(well_dict['vs'][local_mask]))
            print('  Rho: ', type(well_dict['rho']), len(well_dict['rho'][local_mask]))
            print('  Porosity: ', type(well_dict[log_table['Porosity']]), len(well_dict[log_table['Porosity']][local_mask]))
            print('  Initial bulk: ', type(fsc.initial_bulk_gpa), len(fsc.initial_bulk_gpa[lithology_mask]))
            print('  Initial density: ', type(fsc.initial_density_gcc), len(fsc.initial_density_gcc[lithology_mask]))
            print('  Final bulk: ', type(fsc.final_bulk_gpa), len(fsc.final_bulk_gpa[lithology_mask]))
            print('  Final density: ', type(fsc.final_density_gcc), len(fsc.final_density_gcc[lithology_mask]))
            print('  Mineral bulk: ', type(msc.final_bulk_gpa), len(msc.final_bulk_gpa[lithology_mask]))

        if verbose:
            print(mod_history)

        # Notice the use of the 'local_mask' on the well logs, while the 'lithology_mask' is used on the calculated
        # elastic properties
        # Double check that their length matches
        n_1 = len(well_dict['vp'][local_mask])
        n_2 = len(fsc.initial_bulk_gpa[lithology_mask])
        if n_1 != n_2:
            err_txt = 'Length of the masks does not match: {} vs. {}'.format(n_1, n_2)
            print_info(err_txt, 'error', logger, raiser='IOError')

        # Now run the fluid substitution
        _vp_2, _vs_2, _rho_2, _k_2 = gassmann_vel(
            well_dict['vp'][local_mask].to('m/s').magnitude,
            well_dict['vs'][local_mask].to('m/s').magnitude,
            well_dict['rho'][local_mask].to('g/cc').magnitude,
            fsc.initial_bulk_gpa[lithology_mask],
            fsc.initial_density_gcc[lithology_mask],
            fsc.final_bulk_gpa[lithology_mask],
            fsc.final_density_gcc[lithology_mask],
            msc.final_bulk_gpa[lithology_mask],
            well_dict[log_table['Porosity']][local_mask].magnitude
        )

        # Create new vp, vs and rho logs based on copies of the input logs, and replace the original
        # values with the fluid substituted values only where the combined mask of interval and cutoffs are True
        for _type, _result, _result_units in zip(['P velocity', 'S velocity', 'Density'], [_vp_2, _vs_2, _rho_2], ['m/s', 'm/s', 'g/cc']):
            _log = well.get_log_curve(log_table[_type])
            _units = _log.units

            # Create a new name for the fluid substituted log
            _suffix = 'fs_{}'.format(fsc.tag) if fsc.tag is not None else '{}_fs'.format(_log.name)
            _name = '{}_{}'.format(_log.name, _suffix)

            # If the well is new, the new fluid_substituted log should not exist
            if new_well and _name in well.get_log_names:
                err_txt = 'The log {} already exists in well {}'.format(_name, well.name)
                print_info(err_txt, 'error', logger, raiser='IOError')

            # Only copy the LogCurve if the new log doesn't exist within the well, else modify the existing substituted log
            if _name not in well.get_log_names:
                # Copy the existing _log
                fs_log = _log.copy(_suffix)
            else:
                # Get the fluid substituted log
                fs_log = well.get_log_curve(_name)

            # Now replace the original with the fluid substituted results
            fs_log.data[local_mask] = Q_(_result, _result_units).to(_units)

            # Add the new fluid substituted log to the well if it wasn't there before
            if _name not in well.get_log_names:
                well.add_log(fs_log, if_log_exists='ask')

        last_well = well
        last_mod_history += mod_history

    # Save the last well if we have asked for it
    if save_result_folder is not None:
        _tag = '' if result_file_postfix is None else '_{}'.format(result_file_postfix)
        _file_name = os.path.join(save_result_folder, '{}{}.las'.format(last_well.name, _tag))
        print('Saving to {}'.format(_file_name))
        last_well.header.modification_history += last_mod_history
        last_well.write_las(_file_name)

class InteractiveFluidSub:
    """
    A button, and a dialog, for a 'naiv' fluid substitution of the selected LithoFluid in a LithoFluidsTable.
    The name, Vp, Vs and Rho of the selected row are replaced by the results of LithoFluid.fluid_sub(). The rest of the
    row, e.g. the standard deviations, is kept.
    Nothing happens unless exactly one row is selected.
    """
    def __init__(self,
                 cds: ColumnDataSource,
                 litho_fluids: LithoFluids | None = None,
                 update_table: Callable | None = None):
        """
        :param cds:
            ColumnDataSource of the LithoFluidsTable
        :param litho_fluids:
            The LithoFluids of the LithoFluidsTable, used for finding the quasi 2D litho fluids, which can't be replaced
        :param update_table:
            Called after a row has been replaced
        """
        self.cds = cds
        self.litho_fluids = litho_fluids
        self.update_table = update_table
        # The default values of LithoFluid.fluid_sub()
        self.s_w1 = Spinner(title='Initial water saturation', value=1., low=0., high=1., step=0.05)
        self.s_w2 = Spinner(title='Final water saturation', value=0.2, low=0., high=1., step=0.05)
        self.hc_rho = Spinner(title='Hydrocarbon density [g/cm3]', value=0.8, low=0., step=0.01)
        self.hc_k = Spinner(title='Hydrocarbon bulk modulus [GPa]', value=1.152, low=0., step=0.01)
        self.mineral_rho = Spinner(title='Mineral density [g/cm3]', value=2.6, low=0., step=0.01)
        self.mineral_k = Spinner(title='Mineral bulk modulus [GPa]', value=36.6, low=0., step=0.1)
        self.selected = Div()
        self.message = Div(styles={'color': 'red'})
        self.dialog = None

    @property
    def selected_row(self) -> int | None:
        indices = self.cds.selected.indices
        return indices[0] if len(indices) == 1 else None

    def _is_quasi_2d(self, row: int) -> bool:
        if self.litho_fluids is None or row >= len(self.litho_fluids):
            return False
        _lf = self.litho_fluids.litho_fluids[row]
        return any(isinstance(_x, Callable) for _x in [_lf.vp, _lf.vs, _lf.rho])

    def substitute(self, s_w1: pint.Quantity, s_w2: pint.Quantity, hc: dict, mineral: dict) -> str | None:
        """
        Replaces the selected row with the results of the fluid substitution.
        The table is left as it is if it fails

        :param s_w1:
        :param s_w2:
        :param hc:
        :param mineral:
            See LithoFluid.fluid_sub()
        :return:
            None, or a description of why it failed
        """
        row = self.selected_row
        if row is None:
            return 'Select one litho fluid in the table'
        if self._is_quasi_2d(row):
            return 'Litho fluid {} is quasi 2D, and can not be fluid substituted'.format(self.cds.data['name'][row])

        data = self.cds.data
        litho_fluid = LithoFluid(name=data['name'][row], vp=Q_(data['vp'][row], 'm/s'), vs=Q_(data['vs'][row], 'm/s'),
                                 rho=Q_(data['rho'][row], 'g/cm**3'))
        fail_txt = 'The fluid substitution of {} failed, its porosity is zero or undefined. Is its density the same ' \
                   'as the mineral density?'.format(litho_fluid.name)
        try:
            result = litho_fluid.fluid_sub(s_w1, s_w2, hc, mineral)
        except ZeroDivisionError:
            return fail_txt
        values = {'vp': float(result.vp.to('m/s').magnitude), 'vs': float(result.vs.to('m/s').magnitude),
                  'rho': float(result.rho.to('g/cm**3').magnitude)}
        if not all(isfinite(_x) for _x in values.values()):
            return fail_txt

        # The model table finds its litho fluids by name, so the name must be unique
        other_names = [str(_x).lower() for _i, _x in enumerate(data['name']) if _i != row]
        if result.name.lower() in other_names:
            return 'There is already a litho fluid named {}'.format(result.name)

        new_data = dict(data)
        for _key, _value in dict(values, name=result.name).items():
            new_data[_key] = list(data[_key])
            new_data[_key][row] = _value
        self.cds.data = new_data
        if self.update_table is not None:
            self.update_table()
        return None

    def _show_selected(self):
        row = self.selected_row
        self.selected.text = 'Select one litho fluid in the table' if row is None else \
            'Litho fluid: <b>{}</b>'.format(self.cds.data['name'][row])

    def _open_dialog(self):
        if self.selected_row is None:
            print_info('Fluid substitution needs exactly one selected litho fluid', 'warning', logger)
            return
        self._show_selected()
        self.message.text = ''
        self.dialog.visible = True

    def _apply(self):
        inputs = [self.s_w1, self.s_w2, self.hc_rho, self.hc_k, self.mineral_rho, self.mineral_k]
        if any(_x.value is None for _x in inputs):
            self.message.text = 'All values must be given'
            return
        error = self.substitute(
            Q_(self.s_w1.value, ''),
            Q_(self.s_w2.value, ''),
            dict(rho=Q_(self.hc_rho.value, 'g/cm**3'), k=Q_(self.hc_k.value, 'GPa')),
            dict(rho=Q_(self.mineral_rho.value, 'g/cm**3'), k=Q_(self.mineral_k.value, 'GPa')))
        self.message.text = '' if error is None else error
        self.dialog.visible = error is not None

    def _close_dialog(self):
        self.dialog.visible = False

    def draw(self) -> tuple:
        """
        :return:
            The button that opens the dialog, and the dialog, which must be added to a layout to be available
        """
        self.cds.selected.on_change('indices', lambda attr, old, new: self._show_selected())

        apply = Button(label='Apply', button_type='success')
        apply.on_click(self._apply)
        cancel = Button(label='Cancel')
        cancel.on_click(self._close_dialog)
        self.dialog = Dialog(
            title='Fluid substitution',
            content=column(self.selected, row(self.s_w1, self.s_w2), row(self.hc_rho, self.hc_k),
                           row(self.mineral_rho, self.mineral_k), self.message, row(apply, cancel)),
            visible=False,
            close_action='hide')

        button = Button(label='Fluid sub', button_type='success')
        button.on_click(self._open_dialog)
        return button, self.dialog
