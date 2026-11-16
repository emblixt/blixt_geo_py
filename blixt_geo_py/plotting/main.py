# This can be invoked by calling:
# T:\Python\EMB\blixt_geo_py\blixt_geo_py> T:\Python\EMB\blixt_geo_py\.p310\Scripts\python.exe -m bokeh serve --show .\plotting


from bokeh.plotting import column, figure, show, curdoc, row


# test = 'log_plotter__test_cutoffs'
# test = 'log_plotter__test_well_plotter_with_cutoffs'
# test = 'cross_plotter__test_working_intervals'
# test = 'cross_plotter__test_both'
# test = 'rp_plotter__test_well'
# test = 'rp_plotter__test_well_with_rpt'
test = 'templates_table__test_dialog'
# test = 'plot_logs__test_compare_model_with_well'


if test == 'log_plotter__test_cutoffs':
    from blixt_geo_py.unit_tests import test_log_plotter
    test = test_log_plotter.TestCases()
    grid, table, table_buttons, apply_mask, reset_mask = test.test_cutoffs(unit_test=False)
    curdoc().add_root(
        row(
            grid, column(
                table,
                row(table_buttons, apply_mask, reset_mask)
            )
        )
    )
elif test == 'log_plotter__test_well_plotter_with_cutoffs':
    from blixt_geo_py.unit_tests import test_log_plotter
    test = test_log_plotter.TestCases()
    grid, table, table_buttons, apply_mask, reset_mask = (
        test.test_well_plotter_with_cutoffs(unit_test=False))
    curdoc().add_root(
        row(
            grid, column(
                table,
                row(table_buttons, apply_mask, reset_mask)
            )
        )
    )
elif test == 'cross_plotter__test_working_intervals':
    from blixt_geo_py.unit_tests import test_cross_plotter
    test = test_cross_plotter.TestCases()
    xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, wis_guis = test.test_working_intervals()
    curdoc().add_root(
        row(
            column(
                xplot,
                row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask),
            ),
            column( wis_guis  # ,
                   )
        )
    )

elif test == 'cross_plotter__test_both':
    from blixt_geo_py.unit_tests import test_cross_plotter
    test = test_cross_plotter.TestCases()
    xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = test.test_both()
    curdoc().add_root(
       row(
          column(
              xplot,
              row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask),
          ),
          column(ct_guis[0],
                 ct_guis[1],
                 wis_guis
                 )
       )
    )

elif test == 'rp_plotter__test_well':
    from blixt_geo_py.unit_tests import test_rp_plotter
    test = test_rp_plotter.TestCases()
    xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis, style_table\
        = test.test_well(unit_test=False)
    curdoc().add_root(
        row(
            column(
                xplot,
                row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask)
            ),
            column(style_table,
                   column(ct_guis[0], ct_guis[1]),
                   column(wis_guis)
                   )
        )
    )

elif test == 'rp_plotter__test_well_with_rpt':
    from blixt_geo_py.unit_tests import test_rp_plotter
    test = test_rp_plotter.TestCases()
    (xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis, style_table,
     rpt_dt, add_row, var_select, delete_row, update_table) = test.test_well_with_rpt(unit_test=False)
    curdoc().add_root(
        row(
            column(
                xplot,
                row(x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask)
            ),
            column(style_table,
                   column(ct_guis[0], ct_guis[1]),
                   column(wis_guis),
                   column(
                       rpt_dt, row(add_row, var_select, delete_row, update_table)
                   )
           )
        )
    )

elif test == 'plot_logs__test_compare_model_with_well':
    from blixt_geo_py.unit_tests import test_plot_logs
    test = test_plot_logs.TestPlot()
    layout, data_table, lf_table, lf_controls, model_table, model_controls = (
        test.test_compare_model_with_well(unit_test=False))
    curdoc().add_root(
        column(
            layout,
            row(
                column(model_table, model_controls),
                column(lf_table, lf_controls)
            ),
            data_table
        )
    )

elif test == 'templates_table__test_dialog':
    # The templates dialog linked to a WellPlotter and a CrossPlotter. The Save button writes to the project table,
    # so it is saved to a copy of it
    import os
    import shutil
    import tempfile
    from blixt_geo_py.unit_tests.test_log_plotter import make_well_data, project_table
    from blixt_geo_py.plotting.log_plotter import WellPlotter
    from blixt_geo_py.plotting.cross_plotter import CrossPlotter
    from blixt_geo_py.core.templates_table import ProjectTemplatesTable, log_types_of
    table_copy = os.path.join(tempfile.mkdtemp(), 'project_table.xlsx')
    shutil.copy2(project_table, table_copy)
    print('The templates are saved to {}'.format(table_copy))
    templates = ProjectTemplatesTable(table_copy)
    well, cutoffs = make_well_data()
    well_plot = WellPlotter(well, [['vsh'], ['phie'], ['vp_dry', 'vp_sg08']])
    grid = well_plot.draw(title=well.name)
    well_plot.link_templates(grid, templates.log_cds)
    ds = well.data_source()
    xp = CrossPlotter({ds.name: ds}, x='vp_dry', y='phie')
    x_cds = xp.cds
    xplot, x_menu, y_menu, size_menu, color_menu, apply_mask, reset_mask, ct_guis, wis_guis = xp.draw(x_cds)
    style_table = xp.add_data_source_style(x_cds)
    xp.link_templates(x_cds, templates.log_cds, templates.well_cds, log_types=log_types_of(well))
    curdoc().add_root(
        column(
            templates.widget(),
            row(grid, column(xplot, row(x_menu, y_menu), style_table))
        )
    )
