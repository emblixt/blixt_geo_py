"""
Common settings for the unit tests that create plots.

Import this module in every test module that creates plots, before any plots are made, e.g.
    from blixt_geo_py.unit_tests.plot_settings import show_plots, show_or_close

Set the environment variable BLIXT_SHOW_PLOTS=1, or set show_plots to True below, to view the plots created by the
tests. Off by default, so running the whole test suite doesn't stop at every plot window, or open a browser tab for
every bokeh plot.

When the plots are not shown, this also applies to plots that are shown from inside the library code:
- matplotlib uses the non-interactive Agg backend, so plt.show() does not open any windows
- bokeh's show() still writes the html file, so that errors in the layout are still caught, but it does not open
  the file in a browser
"""
import os
import warnings

import matplotlib

show_plots = os.environ.get('BLIXT_SHOW_PLOTS', '0') == '1'
# show_plots = True

if not show_plots:
    matplotlib.use('Agg')
    # plt.show() warns that the Agg backend cannot show the plots, which is exactly what we want
    warnings.filterwarnings('ignore', message='FigureCanvasAgg is non-interactive')
    # Read by bokeh each time show() is called. 'none' makes bokeh skip opening the browser
    os.environ['BOKEH_BROWSER'] = 'none'


def show_or_close():
    """
    Shows the open matplotlib figures if show_plots is True, otherwise closes them, so that they don't pile up in
    memory while the tests run
    """
    import matplotlib.pyplot as plt
    if show_plots:
        plt.show()
    else:
        plt.close('all')
