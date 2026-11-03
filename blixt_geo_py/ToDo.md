**ToDo**

###### 2022-10-10

Add the following usages to the different introduction notebooks
 - Depth trends, and how to use them
 - Checkshots
 - well paths
 - EEI
 - models

##### 2022-12-15

~~Modify and generalize the import of data to a Block and to a Well so that we don't need to have both read_las() and read_log_data()~~ 


##### 2023-03-15
~~Modify the Param data class rp_core, so that it follows the "standard" used in the LogCurve object (e.g. "data" vs, "value").~~

~~We could think about adding a "style" element to both LogCurve, Well & Param classes, so that we are less dependent on using the "template" dictionary everywhere.~~

Look into the possibility of using calculated masks, using calc_mask(), and their name & description, instead of sending around cutoffs and cutoff strings. 
Many functions could use a mask, and its description, as input. See blixt_rp.rp_utils.calc_toc.calc_toc() as example

##### 2023-03-20
~~Move LogCurve class in to well.py~~

~~Get rid of the "AttribDict" thing~~

~~Make "start", "stop", and "step" mandatory items of the LogCurve object too~~

~~Add a "write_las" function to both LogCurves, Blocks, and Wells (one lasfile per block)~~

#### 2025-11-10 
Move rp_core.py functions to rp_core_new and let them use Pint instead of params

Figure out why the LithoFluidsTable doesnt work in avo_chi_plotter.py

Merge the WorkingIntervalsTable of core.py into the add_strat_table() in log_plotter.py

~~Try to replace the python callback that is used for line adding / removal in the different Tables to a CustomJS callback~~

### 2025-12-30
~~Update models.py so that we don't need both the older Model and Layer class AND the newer ModelTable and ModelLayer
(Merge)~~

### 2026-02-03
Use the lasio package to deal with reading and writing .las files instead of self-built programs. It can read wrapped 
files and will be updated to deal with las 3 format that is coming.
Use the Agile Geoscience bruges library for wavelets, filters and rock physics instead of self-built programs. It is no
longer developed from Agile Geoscience, but it is maintained by volunteers (seldomly). Write a wrapper so that it takes 
pint units into use. 

### 2026-10-29
- ~~Clean up / Remove all the unused "calc_stats" functionality - it is only obstructing~~
- ~~Make Project to ignore the "Use well" (Yes/No) column in the project_table.xlsx, and instead specify in the call which wells to use~~ (Project.load_wells())
  - ~~Make this optional, so that the old method still works~~
- ~~Take use of the new environmental variable "show_plots" in all unit tests that creates plots~~ (unit_tests/plot_settings.py)
- Figure out how to use the de_trend functionality in calc_statistics, and apply it 
- ~~Remove the dependency of the old "convert_data" function~~ (replaced by pint)
- Put pint into proper use throughout the code
- In rp_core.py and rp_wrapper.py clarify which type of pressure the functions depend on, effective or pore pressure. And CORRECT any mistakes
- ~~Let Claude have a look at project.py, fix weak code and suggest that Project also should set up a results folder ("results_folder")~~
- ~~Port plot_rp and test_rp to the current Well API~~
- ~~Move handle_template, default_templates and get_from_template into the Template class~~ (Template.from_dict(), 
  Template.plot_settings() and Template.default_templates())
- ~~Fix the "Models must be owned by only a single document" error when making several bokeh plots~~ (default_tools())
- ~~Remove fluids.py, minerals.py and rp_core.run_fluid_sub()~~ (replaced by fluids_and_minerals.py and 
  fluid_substitution.py)
- calc_elastics.calc_ai_around_top() fails without templates, as the default templates lack 'Impedance', 
  'P velocity' and 'Density'
- StatsCalculation.well_style() reads line_color, but the well colour from the project table is in fill_color
- ~~Port test_masking to the current Well API~~
- ~~Let masks.create_mask() accept limits without units, and stop its false warning for lists of pint Quantities~~
- ~~Remove the pre-pint Param class (param.py)~~
- ~~Fix the creation_date and modification_date of Header~~ (part of replacing AttribDict)
- ~~Port, or mark as old, the code that uses the old Well API (Well.block)~~ (test_io, test_plots and 
  helpers.plot_one_column() are ported)
  - ~~Delete, or port, the code that is marked "OLD Well API": io.write_las(), calc_elastics.test_calc_elastics(), and
    the commented out code in well.py~~ (deleted)
- ~~Let LogTable handle mixed single log names and lists of log names, so that read_las() can read them~~
- ~~Cutoffs.use_log_table() does not support multi log LogTables~~
- test_well and test_plot_logs read las files from T:\ and OneDrive, and one test waits for input()
- LogPlotter.add_cutoffs_table() is called with a 'rules' argument it does not have (test_plot_logs)
- unit_tests/main.py imports test_models, which it can't find

### 2026-11-02
- ~~Add a new Bokeh interactive tool that can do a "naiv" fluid substitution  on a selected LithoFLuid in a LithoFluidTable. It is actually initiated in InteractiveFluidSub in fluid_substitution.py~~ (the "Fluid sub" button of LithoFluidsTable)
- ~~Add an option to not display the well synthetics in the compare_synth_with_seismic~~ (already there, ignore_well_synth)
- ~~Allow StatsCalculation to be run without cutoffs, so that it simply calculates the statistics of a whole interval, regardless of lithology~~ (cutoffs is now optional, and comes after log_table)
- ~~Make a fix so that everywhere a Multi log LogTable is used where it is not supported, we raise a warning and just take the first of the given logs~~ (asks the user for the index of the log to use instead, LogTable.select_log() and LogTable.single_log())
- ~~If there are more than 5 intervals in plot_logs_vs_burial_depth(), split the plot into one figure per 5 intervals~~ (max_intervals)
- ~~StatsCalculation() doesn't handle the case where one interval is repeated but with different cutoffs (e.g. one for sand, and one for shale), or maybe the case I was testing didn't have any data for one of the cutoffs?~~ (each needs its own suffix)
- ~~Calibrate the Gardner equation (rho = a * Vp^b), within each interval and cutoff range (do it by taking the natural logarithm, then you get a linear regression problem)~~ (StatsCalculation.gardner(), save_gardner(), plot_gardner() and read_gardner())

### Collected in-code ToDo's
Collected on 2026-11-03. Each item gives the file (relative to this folder), the line, and the class / function it belongs to. The line numbers will drift as the code changes, so trust the class / function name over the line number. The original comments are still visible in commit 8f67956.

- `analysis/calc_elastics.py:121`, calc_ai_around_top(): Check that axes never are used as input. The commented out check of the axes is still in the code here
- `core/core.py:2219`, LithoFluid.fluid_sub(): Insert a test of k_dry
- `core/core.py:2539`, LithoFluidsTable.draw.update_table_function(): I suspect this doesn't work correctly when adding a new row when we're having a Quasi 2D litho fluid
- `core/log_curve.py:638`, LogCurve.take_sampling_from(): Make sure this works correctly for log curves of different sampling and start and stop!
- `core/log_curve.py:1259`, LogCurve.de_trend(): Here the self.min & max function have lost their units?!
- `core/models.py:152`, plot_1d(): We have said that the realize function need resolution in time domain - but it is not fully consistent. See the two items marked REALIZATION below
- `core/models.py:231`, plot_1d(): The realization returns the twt, but the y axis is labelled 'Z [m]'. A commented out 'TWT [s]' label is still in the code here
- `core/models.py:293`, plot_wiggles(): We can make the 'distance between min & max' more robust, so that it works more correctly for "non-symmetric" wedge models
- `core/models.py:469`, plot_wiggles(): The Z position of the annotation is not entirely correct, as we have hard-coded it to use the first vector of the Z array
- `core/models.py:1244`, Model.realize_model(): REALIZATION: What about models in TWT?
- `core/models.py:1256`, Model.realize_model(): REALIZATION: Calculation of this_z. A commented out alternative is still in the code here
- `core/models.py:1469`, ModelTable.realize(): Sometimes I get a "TypeError: float() argument must be a string or a real number, not 'datetime.datetime'" when using this_rho.magnitude here. But when I first write it out, it doesn't occur??!!
- `core/models.py:1548`, ModelTable.draw.update_table_function(): It doesn't seem to catch if I change name of a layer correctly. The names are updated in the table, but if I by mistake had several layers with the same name and case, I can't fix that interactively
- `core/models.py:1601`, ModelTable.draw.update_table_function(): Unsure if the name of the lithofluid will update correctly
- `core/models.py:1948`, LaminarModel.draw_2d(): The lateral resolution selector (dx_selector) was just inserted. Needs work to be put in use
- `core/models.py:2021`, LaminarModel.draw_2d(): Tried to plot the physical x axis range when dx is given. It works (the commented out code is still here), but adds two follow-up problems: 1. The x-axis range does not update when we change dx interactively. 2. The trace-index selector needs to be updated too
- `core/models.py:2453`, FaultModel.__init__(): We are moving the parameters dx and n_traces to the mother LaminarModel object
- `core/models.py:2782`, tuning_wedge_analysis(): Double check that it should be domain='TWT' in the call to build_wedge()
- `core/models.py:2870`, laminar_model_analysis(): Try using a shared y axis for the wiggle and model axes
- `core/models.py:3245`, update_1d_model_function(): Handle the situation when a case is removed. Only adding a new case is handled, for now
- `core/models.py:3314`, update_2d_model_function(): Handle the situation when a case is removed. Only adding a new case is handled, for now
- `core/seismic.py:104`, SeismicTraces: Suggested major re-write: Rename this to something like "SeismicSection", and make StochasticSyntheticTraces and AvoAmplitudes methods of this class. Add more attributes, e.g. "incident_angle", "chi_angle" which can be used for near, mid and far-stacks and so on. Also add a model as a non-mandatory attribute, so that the seismic section can be calculated from this model. Also, make the output seismic sections from models.py of this type
- `core/seismic.py:303`, AvoAmplitudes.calc_eei(): The model parameter: Maybe we should restrict ourselves to LaminarModel and WedgeModel only
- `core/seismic.py:413`, AvoAmplitudes.calc_amplitudes(): The model parameter: Maybe we should restrict ourselves to LaminarModel and WedgeModel only
- `core/seismic.py:751`, AvoAnalyzer.cds(): At present, the AvoAnalyzer cant handle name changes of the points
- `core/seismic.py:1824`, seismic_data_plot(): The seismic seems upside down! (the p.image() call)
- `core/well.py:647`, Well.dict(): Is the depth (= md) log needed in the dictionary? It is commented out, and marked as "TESTING WITHOUT IT"
- `core/well.py:960`, Well.calc_blocked_litho_fluids(): The order of vp, vs, and rho must match the columns of the plot!
- `core/well.py:987`, Well.calc_blocked_litho_fluids(): Seems like the litho_fluids doesn't pick up the STD when running the one_d_model() method
- `io/io.py:1053`, read_sums_and_averages(): Make it skip empty rows
- `io/io.py:1684`, read_petrel_checkshots(): Build in a check to see what the time units are! Now we assume it is in ms. If we correct this, then make sure every usage of read_petrel_checkshots is updated
- `io/io.py:1764`, read_well_headers(): Handle the replaced xml code too (the '<key AAAA> BBBB </key>' sections are now replaced and ignored)
- `io/io.py:1768`, read_well_headers(): Find any strings specifying a lat / lon (e.g 65°55'1.6900"N) and replace with deg, min, sec. A commented out regular expression is still in the code here
- `io/io.py:2225`, well_reader(): well_dict.add_section() will probably fail. Test and compare with 'original' converter
- `io/io.py:2295`, well_reader(): Some las files contain names enclosed in " ", and these names can contain spaces (see S:\Well\Wells_Norway\QUAD_35\35_4-3\Petrophysics\Interpretation\35_4-3_CPI_OUT_2022-11-06.las). And we need to be smart to separate out these somehow. It is done in not-so-smart way in read_petrel_checkshots()
- `io/io.py:2375`, well_excel_reader(): Make it possible to add units and description to data read from Excel files too
- `io/io.py:2433`, interpret_cutoffs_string(): This function can be *REMOVED* because the new CutoffRule and Cutoffs can be generated directly from a string
- `plotting/avo_chi_plotter.py:246`, create_mc_avo_plot(): Do a complete re-write of this function utilizing a 2 layer LaminarModel instead. And after AvoAnalyzer is ready, use that functionality to plot the AVO curves
- `plotting/avo_chi_plotter.py:264`, create_mc_avo_plot(): Try using the new LithoFluidsTable object in core.py instead of create_litho_fluids_table(). It doesn't interact well with the other objects. Needs to be checked. The commented out attempt is still in the code here (see also 2025-11-10)
- `plotting/cross_plotter.py:226`, DataSource.units(): Maybe we should remove '_value is not None', all our data should have units? No, the 'mask' column has no units
- `plotting/cross_plotter.py:288`, DataSource.calc_mask(): Implement calc_mask(), it is only an empty stub
- `plotting/cross_plotter.py:971`, CrossPlotter.drop_down_menus(): The selectors for color axis, marker and legend needs fixing before they can be used properly
- `plotting/cross_plotter.py:1044`, CrossPlotter.add_data_source_style(): The 'order' function in the JS code above works, but Bokeh draws everything in one 'vectorized call', making the order meaningless. A suggested solution by CoPilot is to split the data into different renderers, and then control each of them individually:
  ```python
  # Create one renderer per group
  renderers = {}

  for group in df['group'].unique():
      view = ColumnDataSource(df[df['group'] == group])

      r = p.scatter(
          x='x',
          y='y',
          source=view,
          size='size',
          color='color',
          marker='marker',
          legend_label=group
      )

      renderers[group] = r
  ```
  Then, the JS call back:
  ```javascript
  const renderers = renderer_dict;
  const selected = group_select.value;

  // Move selected renderer to end (top layer)
  const all_renderers = Object.values(renderers);

  // Remove selected
  const others = all_renderers.filter(r => r !== renderers[selected]);

  // Rebuild order
  p.renderers = [...others, renderers[selected]];
  ```
- `plotting/helpers.py:105`, plot_one_column(): fill_between only work when the templates of the data to plot contain min and max value limits
- `plotting/helpers.py:128`, plot_one_column(): Now we take the first log of each log type, generalize this so that it by default takes the first, but can plot all or one specific
- `plotting/helpers.py:664`, annotate_plot(): Remove the hardcoded cyclic coloring of intervals when needed
- `plotting/log_plotter.py:884`, add_strat_table(): Rewrite to reuse the WorkingIntervalsTable class (see also 2025-11-10)
- `plotting/plot_logs.py:174`, plot_chi_rotation(): 1. Check that the logs have the same length and step. 2. The center of the Chi line must update after changing zoom or recalculating the EEI. 3. Create a Class for this. 4. Plot the uncertainty in log AI vs. log GI plot
- `plotting/plot_logs.py:1295`, plot_trends(): We need a x0 for each log type
- `rp/rp_core.py:17`, module level: Make sure that we are certain about the usage of confining and effective pressure, in the whole of rp_core.py (see also 2026-10-29)
- `rp/rp_core.py:1103`, gassmann_vel(): Allow a mask to only do the fluid substitution where the mask is True
- `rp/rp_wrapper.py:387`, rpt_phi_sw(): Insert a test so that 'float' isn't used on the input variables that are arrays or lists
- `unit_tests/test_models.py:133`, TestCase.test_plot(): There is a collision between the "old" and "new" model layers, and the sample_rate
- `unit_tests/test_models.py:143`, TestCase.test_ntg(): This raises an AttributeError. 'Layer' object has no attribute 'ntg'. It is because the Layer has no attribute 'target' on initialization now. To create a 'target' layer we need to have two layers, one base case and one perturbed case, for the same layer. The "old" model interface and plotting will not be able to handle this right now
- `unit_tests/test_models.py:207`, TestCase.test_quasi2d(): At the moment, quasi2d models will likely fail when combining a varying thickness with NTG separate from 1 when Voigt Reuss Hill average is set to False
- `unit_tests/test_plot_logs.py:388`, TestPlot.test_plot_wiggles(): This needs to be rewritten to fulfill the requirement that the CDS is mandatory (the Line() call)
- `unit_tests/test_well.py:387`, WellTestCase.test_one_d_model(): CONTINUE HERE, make sure we actually get a working model out from one_d_model()
- `utils/curve_fitting.py:457`, outlier_weights(): Maybe this method (method=None) removes to much data?? Try using the std
- `utils/masks.py:41`, create_mask(): Force data and limits to be pint Quantities
- `utils/masks.py:61`, create_mask(): The special handling of data in units of 'fract' is a work around, which I hopefully can avoid in the future
- `utils/masks.py:65`, create_mask(): But what if the data is not a pint.Quantity? How do we deal with that? Need to strengthen this. Maybe require that both data and limits are pint.Quantities?
- `utils/signal_analysis.py:71`, smooth(): The window parameter could be the window itself if an array instead of a string
- ~~`utils/utils.py:32`, find_value(): The docstring ended in "But can return the nearest min or max, ... or TODO". Finish the description, or add further 'snap_to' options~~
