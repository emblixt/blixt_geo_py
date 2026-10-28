# This can be invoked by calling:
# T:\Python\EMB\blixt_geo_py\blixt_geo_py> T:\Python\EMB\blixt_geo_py\.p310\Scripts\python.exe -m bokeh serve --show .\rp


from bokeh.plotting import column, figure, show, curdoc, row

from blixt_geo_py.unit_tests import test_rp_wrapper


test = 'rp_wrapper_table'


if test == 'rp_wrapper_table':
    test = test_rp_wrapper.TestCases()
    table, add_row, var_select, delete_row, update_table, _ = test.test_rpt_table()
    curdoc().add_root(
        column(
            table,
            row(add_row, var_select, delete_row, update_table)
        )
    )
