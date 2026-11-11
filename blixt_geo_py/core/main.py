# Interactive bokeh tests of the functionality in the core folder, using the unit tests in unit_tests
# This can be invoked by calling:
# T:\Python\EMB\blixt_geo_py\blixt_geo_py> T:\Python\EMB\blixt_geo_py\.p310\Scripts\python.exe -m bokeh serve --show core


from bokeh.plotting import column, figure, show, curdoc, row


# test = 'seismic__test_avo_qc'
test = 'test_lf_table'
# test = 'test_lf_quasi_2D_table'
# test = 'test_model_table'
# test = 'test_model_table_save'
# test = 'test_laminar_model'
# test = 'test_laminar_model_with_avo_points'
# test = 'test_laminar_q2d_model'
# test = 'test_wedge'
# test = 'test_fault_model'


if test == 'seismic__test_avo_qc':
    from blixt_geo_py.unit_tests import test_seismic
    test = test_seismic.TestCases()
    p, b1, b2, b3, b4, b5, b6, b7, b8 = test.test_avo_qc()
    curdoc().add_root(row(column(row(b1, b2, b3, b4), p, b5), column(b7, b8, b6)))

elif test == 'test_lf_table':
    import blixt_geo_py.unit_tests.test_core as test_core
    test = test_core.LithoFluidTests()
    lf_table, lf_controls = test.test_table(unit_test=False)
    curdoc().add_root(
        column(
            lf_table,
            lf_controls
        )
    )

elif test == 'test_lf_quasi_2D_table':
    import blixt_geo_py.unit_tests.test_core as test_core
    test = test_core.LithoFluidTests()
    lf_table, lf_controls = test.test_quasi_2D_table(unit_test=False)

    def print_table_keys():
        print(lf_table.children[1].source.data.keys())

    lf_controls.children[2].on_click(print_table_keys)
    curdoc().add_root(column(lf_table, lf_controls))

elif test == 'test_model_table':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    model_table, model_controls, lf_table, lf_controls = test.test_quasi2d(unit_test=False)
    curdoc().add_root(
        row(
            column(model_table, model_controls),
            column(lf_table, lf_controls)
        )
    )

elif test == 'test_model_table_save':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    model_table, model_controls, lf_table, lf_controls = test.test_save_model(unit_test=False)
    curdoc().add_root(
        row(
            column(model_table, model_controls),
            column(lf_table, lf_controls)
        )
    )

elif test == 'test_laminar_model':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    title, model_table, model_controls, lf_table, lf_controls, grid, controls \
        = test.test_laminar_model(unit_test=False)
    curdoc().add_root(
        column(title, grid, controls,
               row(
                   column(model_table, model_controls),
                   column(lf_table, lf_controls)
               ))
    )

elif test == 'test_laminar_model_with_avo_points':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    (title, model_table, model_controls, lf_table, lf_controls, grid, controls,
     points_table, update_avo, avo_figure, ixg_figure, eei_figure, chi_input, avo_cds) \
        = test.test_laminar_model_with_avo_points(unit_test=False)
    curdoc().add_root(
        row(
            column(
                column(title, grid, sizing_mode='stretch_width'),
                controls,
                row(
                    column(model_table, model_controls),
                    column(lf_table, lf_controls)
                )
            ),
            column(points_table, row(update_avo, chi_input), avo_figure, ixg_figure, eei_figure)
        )
    )

elif test == 'test_laminar_q2d_model':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    title, model_table, model_controls, lf_table, lf_controls, grid, controls\
        = test.test_laminar_q2d_model(unit_test=False)
    curdoc().add_root(
        column(title, grid, controls,
                    row(
                        column(model_table, model_controls),
                        column(lf_table, lf_controls)
                    ))
    )

elif test == 'test_wedge':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    (title, model_table, model_controls, lf_table, lf_controls, grid, controls, new_grid, points_table, update_avo,
     avo_figure, ixg_figure, eei_figure, chi_input) = test.test_wedge(unit_test=False)
    curdoc().add_root(
        row(
            column(title, grid, controls, new_grid,
                   row(
                       column(model_table, model_controls),
                       column(lf_table, lf_controls)
                   )
                   ),
            column(points_table, row(update_avo, chi_input), avo_figure, ixg_figure, eei_figure)
        )
    )

elif test == 'test_fault_model':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    (title, lf_table, lf_controls, model_table,
     model_controls, grid,
     controls, synth_2d_cds,
     dip_selector, throw_selector, n_traces_selector, dx_selector) = test.test_fault_model(unit_test=False)

    curdoc().add_root(
            row(
                column(
                    column(title, grid, sizing_mode='stretch_width'),
                    controls,
                    row(
                        column(model_table, model_controls),
                        column(lf_table, lf_controls)
                    )),
                column(dip_selector, throw_selector, n_traces_selector, dx_selector)
            )
    )
