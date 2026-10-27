# This can be invoked by calling:
# T:\Python\EMB\blixt_geo_py\blixt_geo_py> T:\Python\EMB\blixt_geo_py\.p310\Scripts\python.exe -m bokeh serve --show .\rp


from bokeh.plotting import column, figure, show, curdoc, row


test = 'rp_wrapper_table'


if test == 'rp_wrapper_table':
    test = rp_wrapper_new.TestCases()
    table, add_row, delete_row, update_table = test.test_rpt_table()
    curdoc().add_root(
        column(
            table,
            row(add_row, delete_row, update_table)
        )
    )
