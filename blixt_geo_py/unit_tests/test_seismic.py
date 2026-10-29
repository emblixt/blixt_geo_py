import pickle
import unittest

# Imported before any plots are made. Set BLIXT_SHOW_PLOTS=1 to view the plots, see plot_settings.py
from blixt_geo_py.unit_tests.plot_settings import show_or_close

from bokeh.models import ColumnDataSource, DataTable, PointDrawTool, TableColumn
from bokeh.plotting import column, figure, row, show
from scipy.optimize import least_squares
import matplotlib.pyplot as plt
import numpy as np
import pint

import blixt_geo_py.utils.curve_fitting as mycf
import blixt_geo_py.io.io as uio
import blixt_geo_py.plotting.crossplot as xp
from blixt_geo_py.core.core import LogTable, Template
from blixt_geo_py.core.log_curve import read_las
from blixt_geo_py.plotting.helpers import wiggle_plot
from blixt_geo_py.core.seismic import (AngleStack, AvoAnalyzer, SeismicTraces, StochasticSyntheticTraces,
                                       VolumeOfInterest, add_i_g_point, add_seismic_to_figure, avo_ig, avo_qc,
                                       closest, create_seismic_figure, interpolate_along_offset,
                                       picks_from_seismic_cds, read_zgy, seismic_color_map, seismic_data_plot,
                                       straight_line)


def make_avo_analyzer_data(section_type: str | None = None, synthetic: bool = False):
    # Determine if input is of either section type 'real', 'avo' or 'synthetic'
    if section_type is None:
        section_type = 'avo section'
    model = None

    idx_refl = None
    refl_points = None
    if section_type == 'line section' and not synthetic:
        near = AngleStack('near',
                          "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-NEARSTACK_MIG-FIN_16bit.zgy",
                          angle=10.)
        mid = AngleStack('mid',
                         "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-MIDSTACK_MIG-FIN_16bit.zgy",
                         angle=18.)
        far = AngleStack('far',
                         "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-FARSTACK_MIG_FIN_16bit.zgy",
                         angle=26.)
        ufar = AngleStack('ufar',
                          "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-UFARSTACK_MIG-FIN_16bit.zgy",
                          angle=34.)
        angle_stacks = [near, mid, far, ufar]

        voi = VolumeOfInterest(
            range(4640, 5243, 1),
            range(32253, 32255, 1),
            range(2616, 5108, 4) )

        line_n = 32254
        line_direction = 'xline'  # or 'inline'
        seismic_cds = None
        p = None
        c_amp = None

    elif section_type == 'line section' and synthetic:
        from blixt_geo_py.core.models import WedgeModel
        model = WedgeModel(n_traces=51)
        (title, lf_table, lf_controls, model_table, model_controls, grid, controls,
         seismic_cds) = model.draw_2d()
        p = grid
        c_amp = None
        refl_points = None

    elif section_type == 'avo section' and not synthetic:
        refl_points = []
        _synts = StochasticSyntheticTraces()
        synts = _synts.get_traces(simulate_avo=True)
        idx_refl = _synts.idx_refl
        seismic_cds = ColumnDataSource({'value': [synts.T]})
        p = create_seismic_figure(600, 400)
        c_amp = add_seismic_to_figure(p, seismic_cds, np.arange(40), np.arange(5000))
        if idx_refl is not None:
            depth = np.linspace(0., 5000., seismic_cds.data['value'][0].shape[0])
            for _j in idx_refl:
                print('XXX, idx_refl: {}, in depth: {}, and in inverted depth {}'.format(_j, depth[_j], 5000. - depth[_j]))
                refl_points.append([20., depth[_j]])

    elif section_type == 'avo section' and synthetic:
        from blixt_geo_py.core.models import LaminarModel
        model = LaminarModel()
        (title, lf_table, lf_controls, _model_table,
         model_controls, grid, freq_slider, synth_cds_base) = model.draw()
        p = grid
        seismic_cds = synth_cds_base
        c_amp = None

    else:
        raise IOError('Wrong section type ({}) and synthetic ({}) provided'.format(section_type, synthetic))

    return p, seismic_cds, c_amp, refl_points, model


class TestCases(unittest.TestCase):

    def test_seismic_data_plot(self):
        # p = seismic_data_plot('seismic section')
        p = seismic_data_plot('avo section')
        show(p)

    def test_interpolate(self):
        from blixt_geo_py.plotting.log_plotter import LogColumn, LogPlotter
        las_file = "C:\\Users\\emb\\OneDrive - Petrolia NOCO AS\\Technical work\\Tampen\\Wells\\34_3_3S_seismic.las"
        # las_file = "G:\\My Drive\\Work - Current and Recent\\GeoMind\\Clients\\AkerBP\\PL932 Kaldafjell AVO feasibility\\Wells\\34_3_3S_seismic.las"
        t = Template(**{'name': 'Seismic', 'units': 'dimensionless', 'line_color': 'b'})
        log_table = LogTable({'Seismic':
                                  ['CGG18M01-NVG-PSDM-ANGLE-NEAR-05-15-TPL932MSMTMADF2denoise2',
                                   'CGG18M01-NVG-PSDM-ANGLE-MID-13-23-TPL932MSMTMADF2denoise2',
                                   'CGG18M01-NVG-PSDM-ANGLE-FAR-21-31-TPL932MSMTMADF2denoise2',
                                   'CGG18M01-NVG-PSDM-ANGLE-ULTRAFAR-29-39-TPL932MSMTMADF2denoise2'
                                   ]})
        rename_logs = {
            'near': ['CGG18M01-NVG-PSDM-ANGLE-NEAR-05-15-TPL932MSMTMADF2denoise2'],
            'mid': ['CGG18M01-NVG-PSDM-ANGLE-MID-13-23-TPL932MSMTMADF2denoise2'],
            'far': ['CGG18M01-NVG-PSDM-ANGLE-FAR-21-31-TPL932MSMTMADF2denoise2'],
            'ufar': ['CGG18M01-NVG-PSDM-ANGLE-ULTRAFAR-29-39-TPL932MSMTMADF2denoise2']
        }
        log_curves, well_info = read_las(las_file, log_table=log_table, template=t, rename_logs=rename_logs)

        offset_angles = pint.Quantity(np.array([10., 18., 26., 34.]), 'deg')
        traces = np.zeros((len(offset_angles), len(log_curves['near'])))
        traces[0,:] = log_curves['near'].values
        traces[1,:] = log_curves['mid'].values
        traces[2,:] = log_curves['far'].values
        traces[3,:] = log_curves['ufar'].values
        # fig1, ax1 = plt.subplots()
        # ax1.imshow(traces.T, aspect=1./1000)
        st_orig = SeismicTraces(x=offset_angles.magnitude,
                                 y=log_curves['near'].depth.values,
                                 # traces=traces,
                                 traces=None,
                                 cds=ColumnDataSource({'value': [traces.T]}),
                                 trace_type='avo'
                                 )
        lc_orig = LogColumn('orig',
                            seismic_traces=st_orig)

        new_angles = pint.Quantity(np.linspace(10, 34, 100), 'deg')
        new_traces = interpolate_along_offset(traces, offset_angles, new_angles)
        st_intrp = SeismicTraces(x=new_angles.magnitude,
                                 y=log_curves['near'].depth.values,
                                 # traces=new_traces,
                                 traces=None,
                                 cds=ColumnDataSource({'value': [new_traces.T]}),
                                 trace_type='avo')
        lc_intrp = LogColumn('interpolated', seismic_traces=st_intrp)

        plotter = LogPlotter(columns=[lc_orig, lc_intrp])
        grid = plotter.figure()
        show(grid)


        # fig2, ax2 = plt.subplots()
        # ax2.imshow(new_traces.T, aspect=1./100.)
        # plt.show()


    def test_synthetic_traces(self):
        _synts = StochasticSyntheticTraces()
        synts = _synts.get_traces(simulate_avo=True)
        print(synts.shape)
        cds = ColumnDataSource({'value': [synts.T]})
        print(np.min(synts))
        _seismic_color_map = seismic_color_map(min_val=np.min(synts), max_val=np.max(synts))

        p = figure()
        p.image('value', source=cds,
                color_mapper=_seismic_color_map, dh=synts.shape[1], dw=synts.shape[0], x=0, y=0)
        show(p)


    def test_ixg_plot(self):
        fig, axes = plt.subplots(nrows=1, ncols=2)

        with open('C:\\Users\\marten\\Downloads\\angle_traces.dat', 'rb') as input:
            twt, near_trace, mid_trace, far_trace = pickle.load(input)

        i, g, q = avo_ig(np.array([near_trace.values.flatten(), \
                                   mid_trace.values.flatten(), \
                                   far_trace.values.flatten()]), [10., 18., 26.])

        res = least_squares(
            mycf.residuals,
            [1.,1.],
            args=(i, g),
            kwargs={'target_function': straight_line})
        trend_line = 'WS = {:.4f}*I {:.4f} - G'.format(*res.x)
        print(res.status)
        print(res.message)
        print(res.success)
        print(res.fun.shape)

        xp.plot(i, g, cdata=res.fun,
           ctempl = {'full_name': 'Residual', 'colormap': 'seismic', 'min': np.min(res.fun), 'max':np.max(res.fun)},
           title='IL: 6550, XL: 27009\n{}'.format(trend_line),
           fig=fig, ax=axes[0])

        x_new = np.linspace(*axes[0].get_xlim(), 50)
        axes[0].plot(x_new, straight_line(x_new, *res.x), c='r', label='_nolegend_')

        with open('C:\\Users\\marten\\Downloads\\angle_lines.dat', 'rb') as input:
            twt, near_line, mid_line, far_line = pickle.load(input)
        print('Line shape: {}'.format(near_line.values.shape))

        i, g, q = avo_ig(np.array([near_line.values.flatten(), \
                                   mid_line.values.flatten(), \
                                   far_line.values.flatten()]), [10., 18., 26.])

        res = least_squares(
                mycf.residuals,
                [1.,1.],
                args=(i, g),
                kwargs={'target_function': straight_line}
        )
        trend_line = 'WS = {:.4f}*I {:.4f} - G'.format(*res.x)
        print(res.status)
        print(res.message)
        print(res.success)
        print(res.fun.shape)

        xp.plot(i[::100], g[::100], cdata=res.fun[::100],
           ctempl = {'full_name': 'Residual', 'colormap': 'seismic', 'min': np.min(res.fun), 'max':np.max(res.fun)},
           title='IL: 6550\n{}'.format(trend_line),
           fig=fig, ax=axes[1],
           edge_color=False)

        x_new = np.linspace(*axes[1].get_xlim(), 50)
        axes[1].plot(x_new, straight_line(x_new, *res.x), c='r', label='_nolegend_')

        fig, ax = plt.subplots()
        ax.imshow(np.transpose(res.fun.reshape((401, 501))),
                  cmap='seismic',
                  vmin=np.min(res.fun),
                  vmax=np.max(res.fun),
                  interpolation='spline16',
                  aspect='auto',
                  extent=(0,400,3000,1000))

        #X, Y = np.meshgrid(np.arange(0,401,1), twt)
        #ax.pcolormesh(X, Y, np.transpose(res.fun.reshape((401, 501))),
        #          cmap='seismic',
        #          vmin=np.min(res.fun),
        #          vmax=np.max(res.fun),
        #          )
        #ax.invert_yaxis()
        ax.grid(True)
        ax.set_title('Inline: 6550, Residual')
        ax.set_xlabel('X lines')
        ax.set_ylabel('TWT [ms]')
        show_or_close()


    def test_plot_amp_vs_offset(self):
        filename = "U:\\COMMON\\SAAS DEVELOPMENT\\TEST_DATA\\Test_angle_stacks\\KPSDM-NEAR_10deg_cropped.sgy"
        near, nsamples, sr, twt, ntraces, header, ilines, xlines = uio.read_segy(filename, byte_il=189, byte_xl=193)
        filename = "U:\\COMMON\\SAAS DEVELOPMENT\\TEST_DATA\\Test_angle_stacks\\KPSDM-MID_18deg_cropped.sgy"
        mid, nsamples, sr, twt, ntraces, header, ilines, xlines = uio.read_segy(filename, byte_il=189, byte_xl=193)
        filename = "U:\\COMMON\\SAAS DEVELOPMENT\\TEST_DATA\\Test_angle_stacks\\KPSDM-FAR_26deg_cropped.sgy"
        far, nsamples, sr, twt, ntraces, header, ilines, xlines = uio.read_segy(filename, byte_il=189, byte_xl=193)

        inline = 6550
        xline = 27009
        t0 = 1245
        near_trace = near.sel(INLINE=inline, XLINE=xline)
        near_max = np.max(np.abs(near_trace.values))
        mid_trace = mid.sel(INLINE=inline, XLINE=xline)
        mid_max = np.max(np.abs(mid_trace.values))
        far_trace = far.sel(INLINE=inline, XLINE=xline)
        far_max = np.max(np.abs(far_trace.values))
        angs = np.array([10., 18., 26.])
        fig, axes = plt.subplots(nrows=1, ncols=2)


        for a, t in zip(angs, [near_trace, mid_trace, far_trace]):
            wiggle_plot(axes[0], twt, t.values, zero_at=a, scaling=10. / max([near_max, mid_max, far_max]))

        axes[0].axhline(t0)

        ind = np.argmin(abs(near_trace.TWT.values - t0))

        amps = np.array([near_trace.values[ind], mid_trace.values[ind], far_trace.values[ind]])

        i, g, q = avo_ig(amps, angs)

        xp.plot(angs, amps, cdata='b', fig=fig, ax=axes[1])
        _angs = np.linspace(1, angs[-1]+10)
        axes[1].plot(_angs, i + g*np.sin(np.radians(_angs))**2)

        show_or_close()


    def test_plot_line(self):
        filename = "U:\\COMMON\\SAAS DEVELOPMENT\\TEST_DATA\\Test_angle_stacks\\KPSDM-NEAR_10deg_cropped.sgy"
        data, nsamples, sr, twt, ntraces, header, ilines, xlines = uio.read_segy(filename, byte_il=189, byte_xl=193)
        print(header)
        uu={'add_colorbar':False,'robust':True,'interpolation':'spline16'}
        fig, ax = plt.subplots()
        data.plot.imshow(x='XLINE', y='TWT', yincrease=False, ax=ax, **uu)
        show_or_close()


    def test_amp_spectra(self):
        from blixt_geo_py.core.wavelets import plot_cwt
        filename = "U:\\COMMON\\SAAS DEVELOPMENT\\TEST_DATA\\Test_angle_stacks\\KPSDM-NEAR_10deg_cropped.sgy"
        data, nsamples, sr, twt, ntraces, header, ilines, xlines = uio.read_segy(filename, byte_il=189, byte_xl=193)

        inline = 6550
        xline = 27009
        sr0 = 0.004 # sample rate in seconds
        this_trace = data.sel(INLINE=inline, XLINE=xline)
        this_inline = data.sel(INLINE=inline)

        #fig, ax = plt.subplots()
        #ax.plot(this_trace.data, twt)
        #ax.invert_yaxis()
        #ax.set_title('IL {}, XL {}'.format(inline, xline))
        #ax.set_ylabel('TWT')


        #f1, amp1, f_peak1 = fullspec(this_inline.data, sr0)
        #f2, amp2 = ampspec(this_trace.data, sr0, smoothing='median')

        #plot_ampspecs([[f1, amp1, f_peak1], [f2, amp2]], ['Whole inline 6550', 'Smooth single trace'])

        #import pandas as pd
        #dataset = "http://paos.colorado.edu/research/wavelets/wave_idl/sst_nino3.dat"
        #df_nino = pd.read_table(dataset)
        #N = df_nino.shape[0]
        #t0=1871
        #sr0=0.25
        #time = np.arange(0, N) * sr0 + t0
        #signal = df_nino.values.squeeze()

        waveletname = 'cmor'
        desired_freqs = np.linspace(1, 1./(2 * sr0), 10)
        # scales, fs = freq2scale(desired_freqs, waveletname, sr0)
        scales = np.arange(1, 128)
        plot_cwt(twt / 1000., this_trace.values, scales, waveletname=waveletname, cmap='jet')
        #plot_cwt(time/1000., signal, desired_freqs)
        # try extracting the scales corresponding to above frequencies
        #scales, fs = freq2scale(desired_freqs, 'morl', sr0)
        ##widths = np.linspace(2, 80, 41)  # pywt.scale2frequency('morl', 2)/0.004 = 101.6 which is less than 125
        #cwtmatr, freqs = pywt.cwt(this_trace.data, scales, 'morl', sr0)

        #X, Y = np.meshgrid(freqs, twt)

        #fig2, ax2 = plt.subplots()
        #ax2.contourf(X, Y, abs(cwtmatr.transpose()),
        #           cmap='jet',
        #           #vmax=abs(cwtmatr).max(),
        #           #vmin=-abs(cwtmatr).max()
        #           vmax=np.max(abs(cwtmatr)),
        #           vmin=np.min(abs(cwtmatr))
        #           )
        #ax2.invert_yaxis()
        #ax2.set_title('IL {}, XL {}'.format(inline, xline))
        #ax2.set_ylabel('TWT')
        #ax2.set_xlabel('Frequency [Hz]')
        #ax2.grid(True)
        show_or_close()


    def test_read_zgy(self):
        f = "R:\\3D\\UTM31\\Acquired Data\\CGG23M03_NVG22PH1_BRAGE\\CGG18M01_NVG_Final_Ki-PreSDM_Z_VVertical_5.3.0.zgy"
        zgy = read_zgy(f, range(6204, 6264, 6), range(21688, 23600, 8), range(500, 1000, 20))  # (10 x 239 x 25)
        print(zgy.keys())

        self.assertTrue(list(zgy.keys()) == ['cdp_x', 'cdp_y', 'data'])

        self.assertTrue(list(zgy['data'].coords.keys()) == ['iline', 'xline', 'samples'])
        self.assertTrue(list(zgy['cdp_x'].coords.keys()) == ['iline', 'xline'])

        # zgy['cdp_x/y'].coords[i/xline] contains the inline, xline numbers
        # E.G:
        self.assertTrue(zgy['cdp_y'].coords['xline'][0] == 21688)

        # The zgy['cdp_x/y'].data contains and numpy array of each i/xline x/y coordinates.
        # E.G:
        self.assertAlmostEqual(zgy['cdp_y'].data[0,0],6701691.7233520)

        # A specific trace can be extracted by
        trace = zgy['data'].data[5, 100]
        self.assertTrue(len(trace) == 25)

        # and its corresponding x and y coordinates
        self.assertAlmostEqual(zgy['cdp_x'].data[5, 100], 498723.94845768646)
        self.assertAlmostEqual(zgy['cdp_y'].data[5, 100], 6711691.625876557)

        # and its corresponding i/x line numbers
        self.assertTrue(zgy['data'].coords['iline'][5], 6234)
        self.assertTrue(zgy['data'].coords['xline'][100], 22488)

        # Whole inline and x-line can be extracted using
        inline_slice = zgy.sel(iline=6234)
        crossline_slice = zgy.sel(xline=22488)

    def test_create_traces_from_zgy(self):
        import blixt_geo_py.plotting.log_plotter as bupp
        f = "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01_NVG21PH1-EW_FINAL_KPSDM_T_FAR_STK_16bit.zgy"
        xline_ranges = range(32253, 32255, 1)
        inline_ranges = range(4640, 5243, 1)
        sample_range = range(2616, 5108, 4)
        zgy = read_zgy(f, inline_ranges, xline_ranges, sample_range)
        xline = zgy.sel(xline=32254)
        x = zgy['data'].coords['iline'].data
        y = zgy['data'].coords['samples'].data
        amps = xline.data
        seis_traces = SeismicTraces(
            x=x,
            y=y,
            traces=amps,
            trace_type='index',
            title='CGG22M01_NVG21PH1-EW_FINAL_KPSDM_T_FAR_STK xline: 32254'
        )
        # seis_traces = SeismicTraces(
        #     x=x,
        #     y=y,
        #     traces=amps.T,
        #     trace_type='index',
        #     title='CGG22M01_NVG21PH1-EW_FINAL_KPSDM_T_FAR_STK xline: 32254'
        # )
        cl = bupp.LogColumn(name='data', seismic_traces=seis_traces)
        # The LogColumn is not the best method for plotting a seismic line this way, as it seems
        # to cause problem for the PointDrawTool
        # lp = bupp.LogPlotter(width=1000, columns=[cl], add_tools=[PointDrawTool()])
        lp = bupp.LogPlotter(width=1000, columns=[cl])
        grid = lp.figure()
        # Try with a PointDrawTool
        cds = ColumnDataSource(dict(
            x=[4700, 4900, 5000], y=[3000, 3500, 4000], color=['red', 'green', 'yellow'] ) )
        renderer = grid.children[0][0].scatter(x='x', y='y', color='color', source=cds, size=10)
        columns = [TableColumn(field="x", title="x"),
                   TableColumn(field="y", title="y"),
                   TableColumn(field='color', title='color')]
        table = DataTable(source=cds, columns=columns, editable=True, height=200)
        draw_tool = PointDrawTool(renderers=[renderer], empty_value='black')
        grid.children[0][0].add_tools(draw_tool)
        grid.children[0][0].toolbar.active_tap = draw_tool
        show(column(grid, table))

    def test_create_seismic_figure(self):
        f = "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01_NVG21PH1-EW_FINAL_KPSDM_T_FAR_STK_16bit.zgy"
        inline_ranges = range(4640, 5243, 1)
        xline_ranges = range(32253, 32255, 1)
        sample_range = range(2616, 5108, 4)
        zgy = read_zgy(f, inline_ranges, xline_ranges, sample_range)
        xline = zgy.sel(xline=32254)
        x = zgy['data'].coords['iline'].data
        y = zgy['data'].coords['samples'].data
        amps = xline.data
        seismic_cds = ColumnDataSource(dict(value=[amps.T]))

        p = create_seismic_figure(900, 600)
        c_amp = add_seismic_to_figure(p, seismic_cds, x, y, title='CGG22M01_NVG21PH1-EW_FINAL_KPSDM_T_FAR_STK')
        # # Test how to access the limits of the colorbar ColorBar
        # print(inspect.getmembers(p._property_values['right'][0].color_mapper))
        # print(p._property_values['right'][0].color_mapper.high)
        # p._property_values['right'][0].color_mapper.high = 50000.


        # Add points
        table, point_cds = add_i_g_point(p, x, y, ['far'])

        show(column(p, row(table, c_amp)))

    def test_avo_qc(self):
        near = AngleStack('near',
                          "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-NEARSTACK_MIG-FIN_16bit.zgy",
                          angle=10.)
        mid = AngleStack('mid',
                          "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-MIDSTACK_MIG-FIN_16bit.zgy",
                          angle=18.)
        far = AngleStack('far',
                          "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-FARSTACK_MIG_FIN_16bit.zgy",
                          angle=26.)
        ufar = AngleStack('ufar',
                          "R:\\3D\\UTM31\\Acquired Data\\CGG22M01-NVG21PH1\\CGG22M01-NVG21PH1-NSRE-FINAL-KPSDM-T-UFARSTACK_MIG-FIN_16bit.zgy",
                          angle=34.)

        voi = VolumeOfInterest(
            range(4640, 5243, 1),
            range(32253, 32255, 1),
            range(2616, 5108, 4) )

        xline = 32254

        return avo_qc([near, mid, far, ufar], voi, line_direction='xline', verbose=True)
        # return avo_qc([near, ufar], voi, xline=xline, verbose=True)

    def test_closest(self):
        x = np.random.normal(10,2, 20)
        x = np.array([int(_x*10) for _x in x])
        # print(np.sort(x))
        print(x)
        print(closest(90.45, x))

    def test_picks(self):
        _synts = StochasticSyntheticTraces(trace_length=500)
        synts = _synts.get_traces(simulate_avo=True)
        cds = ColumnDataSource({'value': [synts.T]})
        _seismic_color_map = seismic_color_map(min_val=np.min(synts), max_val=np.max(synts))
        (m, n) = cds.data['value'][0].shape
        print(synts.shape, m, n )

        p = figure()
        p.image('value', source=cds,
                color_mapper=_seismic_color_map, dh=synts.shape[1], dw=synts.shape[0], x=0, y=0)

        markers = ['asterisk', 'circle', 'cross', 'dash', 'dot', 'square']
        colors = ['black', 'white', 'orange', 'green', 'yellow', 'brown']
        for i, feature in enumerate(['nearest_min']):
        # for i, feature in enumerate(['nearest_min', 'nearest_min_above', 'nearest_min_below']):
        # for i, feature in enumerate(['extract', 'global_max', 'global_min', 'nearest_max', 'nearest_max_above', 'nearest_max_below']):
        # for i, feature in enumerate(['extract', 'global_max', 'global_min', 'nearest_max']):
            if feature in ['global_max', 'global_min']:
                indxs = None
            else:
                indxs = 250

            amps, inds = picks_from_seismic_cds(cds, feature, indxs)
            print(feature, [('{:.2f}'.format(_a), str(_i)) for _a, _i in zip(amps, inds)])

            p.scatter(x=np.arange(n)[::2], y=inds[::2], marker=markers[i], line_color=colors[i],
                      fill_color=colors[i], size=7)

        show(p)

    def test_avo_analyzer(self):
        section_type = 'avo section'
        synthetic = True
        p, seismic_cds, c_amp, refl_points, model = make_avo_analyzer_data(section_type, synthetic)

        analyze_avo = AvoAnalyzer(p, section_type, refl_points, model=model)
        points_cds = analyze_avo.cds
        points_table, update_avo, avo_figure, ixg_figure, eei_figure, chi_input, avo_cds = analyze_avo.draw(points_cds, seismic_cds)


        show(column(p, points_table, update_avo, avo_figure))
