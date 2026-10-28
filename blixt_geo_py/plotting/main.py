# This can be invoked by calling:
# T:\Python\EMB\blixt_geo_py\blixt_geo_py> T:\Python\EMB\blixt_geo_py\.p310\Scripts\python.exe -m bokeh serve --show .\plotting


from bokeh.plotting import column, figure, show, curdoc, row


# test = 'log_plotter__test_cutoffs'
# test = 'log_plotter__test_well_plotter_with_cutoffs'
# test = 'cross_plotter__test_working_intervals'
# test = 'cross_plotter__test_both'
# test = 'rp_plotter__test_well'
test = 'rp_plotter__test_well_with_rpt'


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


