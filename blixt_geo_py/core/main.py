# This can be invoked by calling:
# T:\Python\EMB\blixt_geo_py\blixt_geo_py> T:\Python\EMB\blixt_geo_py\.p310\Scripts\python.exe -m bokeh serve --show core


from bokeh.plotting import column, figure, show, curdoc, row


# test = 'seismic__test_avo_qc'
# test = 'fluid_table'
# test = 'mineral_table'
test = 'test_lf_table'
# test = 'test_laminar_model'
# test = 'test_laminar_q2d_model'
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

elif test == 'test_laminar_model':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    model_table, model_controls, lf_table, lf_controls, grid, controls \
        = test.test_laminar_model(unit_test=False)
    curdoc().add_root(
        column(grid, controls,
               row(
                   column(model_table, model_controls),
                   column(lf_table, lf_controls)
               ))
    )

elif test == 'test_laminar_q2d_model':
    import blixt_geo_py.unit_tests.test_models as test_models
    test = test_models.TestCase()
    model_table, model_controls, lf_table, lf_controls, grid, controls\
        = test.test_laminar_q2d_model(unit_test=False)
    curdoc().add_root(
        column(grid, controls,
                    row(
                        column(model_table, model_controls),
                        column(lf_table, lf_controls)
                    ))
    )

elif test == 'mineral_table':
    from blixt_geo_py.unit_tests import test_minerals
    test = test_minerals.TestCases()
    table, add_row, delete_row, update = test.test_mineral_table(unit_test=False)
    curdoc().add_root(column(table, row(add_row, delete_row, update)))

elif test == 'fluid_table':
    from blixt_geo_py.unit_tests import test_fluids
    test = test_fluids.TestCases()
    table, add_row, delete_row, update = test.test_fluid_table(unit_test=False)
    curdoc().add_root(column(table, row(add_row, delete_row, update)))

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
