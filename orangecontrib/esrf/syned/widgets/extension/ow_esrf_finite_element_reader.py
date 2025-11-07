"""
OASYS2 / AnyQt port of FiniteElementReader
- Converts PyQt5 -> AnyQt (compatible with PyQt6 / PySide6 backends)
- Updates OASYS1 imports to oasys2.widget.* layout
- Keeps matplotlib plotting (FigureCanvasQTAgg) and silx Plot2D

If you hit import errors, paste the traceback and I'll patch quickly.
"""

import os
import sys
import numpy

from AnyQt import QtGui
from AnyQt.QtCore import QRect, Qt
from AnyQt.QtWidgets import QApplication, QLabel, QSizePolicy, QMessageBox
from AnyQt.QtGui import QPixmap, QTextCursor

from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Output

from oasys2.widget import gui as oasysgui
from oasys2.widget.widget import OWWidget
from oasys2.widget.util.widget_util import EmittingStream
from oasys2.widget.util import congruence

from oasys2.widget.util.widget_objects import OasysSurfaceData
from oasys2.widget.util.widget_util import write_surface_file

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from orangecontrib.esrf.syned.util.FEA_File import FEA_File
import orangecanvas.resources as resources
from silx.gui.plot import Plot2D

from srxraylib.metrology.profiles_simulation import slopes


class FiniteElementReader(OWWidget):

    name = "Surface / Finite Element reader"
    description = "Syned: Surface / Finite Element reader"
    icon = "icons/hhlo.png"
    maintainer = "M. Sanchez del Rio"
    maintainer_email = "srio@esrf.eu"
    priority = 10
    category = "Data File Tools"
    keywords = ["data", "file", "load", "read", "FEA", "Finite Elements"]

    class Outputs:
        SurfaceData = Output("Surface Data", OasysSurfaceData)
        DABAM1DProfile = Output("DABAM 1D Profile", numpy.ndarray)

    want_main_area = 1
    want_control_area = 1

    MAX_WIDTH = 1320
    MAX_HEIGHT = 700

    IMAGE_WIDTH = 860
    IMAGE_HEIGHT = 645

    CONTROL_AREA_WIDTH = 405
    TABS_AREA_HEIGHT = 650

    file_in = Setting("")
    file_in_type = Setting(0)
    file_factor_x = Setting(1.0)
    file_factor_y = Setting(1.0)
    file_factor_z = Setting(1.0)

    file_in_skiprows = Setting(0)
    replicate_raw_data_flag = Setting(0)

    file_out = Setting("")
    n_axis_0 = Setting(801)
    n_axis_1 = Setting(500)

    detrended = Setting(0)
    detrended_fit_range = Setting(1.0)
    reset_height_method = Setting(2)
    remove_nan = Setting(0)
    invert_axes_names = Setting(1)
    extract_profile1D = Setting(0)
    coordinate_profile1D = Setting(0.0)
    sigma_flag = Setting(0)
    sigma_axis0 = Setting(10)
    sigma_axis1 = Setting(10)

    display_raw_data = Setting(0)

    fea_file_object = FEA_File()

    usage_path = os.path.join(resources.package_dirname("orangecontrib.esrf.syned.widgets.extension"), "misc", "finite_element_usage.png")

    def __init__(self, show_automatic_box=False):
        super().__init__()

        geom = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(QRect(round(geom.width() * 0.05),
                               round(geom.height() * 0.05),
                               round(min(geom.width() * 0.98, self.MAX_WIDTH)),
                               round(min(geom.height() * 0.95, self.MAX_HEIGHT))))

        self.setMaximumHeight(self.geometry().height())
        self.setMaximumWidth(self.geometry().width())

        tabs_setting = oasysgui.tabWidget(self.controlArea)
        tabs_setting.setFixedHeight(self.TABS_AREA_HEIGHT)
        tabs_setting.setFixedWidth(self.CONTROL_AREA_WIDTH - 5)

        tab_calc = oasysgui.createTabPage(tabs_setting, "Calculate")
        tab_out = oasysgui.createTabPage(tabs_setting, "Output")
        tab_usa = oasysgui.createTabPage(tabs_setting, "Use of the Widget")

        self.tabs_setting = oasysgui.tabWidget(self.mainArea)
        self.tabs_setting.setFixedHeight(self.IMAGE_HEIGHT + 5)
        self.tabs_setting.setFixedWidth(self.IMAGE_WIDTH)
        self.create_tabs_results()

        gui.button(tab_calc, self, "Calculate Interpolated File", callback=self.calculate)

        data_file_box = oasysgui.widgetBox(tab_calc, "Data file", addSpace=True, orientation="vertical")

        figure_box = oasysgui.widgetBox(data_file_box, "", addSpace=True, orientation="horizontal")
        self.le_beam_file_name = oasysgui.lineEdit(figure_box, self, "file_in", "FEA/Surface File/Url:", labelWidth=140, valueType=str, orientation="horizontal")
        gui.button(figure_box, self, "...", callback=self.selectFile)

        data_file_box2 = oasysgui.widgetBox(data_file_box, "", addSpace=True, orientation="horizontal")

        gui.comboBox(data_file_box2, self, "file_in_type", label="File content", labelWidth=220,
                     items=["ALS cols: A X Y Z DX DY DZ",
                            "ESRF cols: X,Y,Z,DX,DY,DZ",
                            "OASYS surface file [hdf5]"],
                     sendSelectedValue=False, orientation="horizontal")

        oasysgui.lineEdit(data_file_box2, self, "file_in_skiprows", "Skip rows:", labelWidth=300, valueType=int, orientation="horizontal")

        data_file_expansion_box = oasysgui.widgetBox(data_file_box, "", addSpace=False, orientation="horizontal")
        oasysgui.widgetLabel(data_file_expansion_box, label="Expansion factor")
        oasysgui.lineEdit(data_file_expansion_box, self, "file_factor_x", "X", labelWidth=10, controlWidth=35, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(data_file_expansion_box, self, "file_factor_y", "Y", labelWidth=10, controlWidth=35, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(data_file_expansion_box, self, "file_factor_z", "Z", labelWidth=10, controlWidth=35, valueType=float, orientation="horizontal")

        gui.comboBox(data_file_box, self, "replicate_raw_data_flag", label="Replicate raw data", labelWidth=220,
                     items=["No", "Along axis 0", "Along axis 1", "Along axes 0 and 1"],
                     sendSelectedValue=False, orientation="horizontal")

        interpolation_box = oasysgui.widgetBox(tab_calc, "Interpolation", addSpace=True, orientation="vertical")
        interpolation_box2 = oasysgui.widgetBox(interpolation_box, "", addSpace=False, orientation="horizontal")

        oasysgui.lineEdit(interpolation_box2, self, "n_axis_0", "Pixels (axis 0)", labelWidth=260, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(interpolation_box2, self, "n_axis_1", "pixels (axis 1)", labelWidth=260, valueType=int, orientation="horizontal")

        gui.comboBox(interpolation_box, self, "remove_nan", label="Remove interp NaN", labelWidth=220,
                     items=["No", "Yes (replace by min height)", "Yes (replace by zero)"],
                     sendSelectedValue=False, orientation="horizontal")

        postprocess_box = oasysgui.widgetBox(tab_calc, "PostProcess", addSpace=True, orientation="vertical")

        gui.comboBox(postprocess_box, self, "detrended", label="Detrend profile", labelWidth=220,
                     items=["None", "Straight line (along axis 0)", "Straight line (along axis 1)",
                            "Best circle (along axis 0)", "Best circle (along axis 1)"],
                     sendSelectedValue=False, orientation="horizontal", callback=self.set_visible)

        self.detrended_fit_range_id = oasysgui.widgetBox(postprocess_box, "", addSpace=True, orientation="vertical")
        oasysgui.lineEdit(self.detrended_fit_range_id, self, "detrended_fit_range", "detrend fit up to [m]", labelWidth=220, valueType=float, orientation="horizontal")

        gui.comboBox(postprocess_box, self, "reset_height_method", label="Reset zero height", labelWidth=220,
                     items=["No", "To height minimum", "To center"], sendSelectedValue=False, orientation="horizontal")

        gui.comboBox(postprocess_box, self, "sigma_flag", label="Gaussian filter", labelWidth=220,
                     items=["None", "Yes"], sendSelectedValue=False, orientation="horizontal", callback=self.set_visible)

        self.sigma_id = oasysgui.widgetBox(postprocess_box, "", addSpace=True, orientation="horizontal")
        oasysgui.widgetLabel(self.sigma_id, label="Gaussian sigma [pixels] axis", labelWidth=350)
        oasysgui.lineEdit(self.sigma_id, self, "sigma_axis0", "0:", labelWidth=0, controlWidth=50, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(self.sigma_id, self, "sigma_axis1", "1:", labelWidth=0, controlWidth=50, valueType=float, orientation="horizontal")

        gui.comboBox(postprocess_box, self, "invert_axes_names", label="Invert axes", labelWidth=120,
                     items=['No', 'Yes'], sendSelectedValue=False, orientation="horizontal")

        profile1D_box = oasysgui.widgetBox(tab_out, "1D profile", addSpace=True, orientation="vertical")
        gui.comboBox(profile1D_box, self, "extract_profile1D", label="Extract and send 1D profile", labelWidth=220,
                     items=["axis 0 (horizontal)", "axis 1 (vertical)"], sendSelectedValue=False, orientation="horizontal")

        oasysgui.lineEdit(profile1D_box, self, "coordinate_profile1D", "At coordinate [m]:", labelWidth=260, valueType=float, orientation="horizontal")

        gui.separator(tab_out, height=20)

        display_box = oasysgui.widgetBox(tab_out, "Display", addSpace=True, orientation="vertical")
        gui.comboBox(display_box, self, "display_raw_data", label="Display Raw data [slow]", labelWidth=220,
                     items=["No", "Yes"], sendSelectedValue=False, orientation="horizontal")

        gui.separator(tab_out, height=20)

        file_info_box = oasysgui.widgetBox(tab_out, "Info", addSpace=True, orientation="vertical")
        tmp = oasysgui.lineEdit(file_info_box, self, "file_out", "Output file name", labelWidth=150, valueType=str, orientation="horizontal")
        tmp.setEnabled(False)

        tab_usa.setStyleSheet("background-color: white;")
        usage_box = oasysgui.widgetBox(tab_usa, "", addSpace=True, orientation="horizontal")

        label = QLabel("")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if os.path.exists(self.usage_path):
            label.setPixmap(QPixmap(self.usage_path))

        usage_box.layout().addWidget(label)

        self.set_visible()

    def set_visible(self):
        if self.detrended == 0:
            self.detrended_fit_range_id.setVisible(False)
        else:
            self.detrended_fit_range_id.setVisible(True)

        if self.sigma_flag == 0:
            self.sigma_id.setVisible(False)
        else:
            self.sigma_id.setVisible(True)

    def create_tabs_results(self):
        tabs_setting = self.tabs_setting
        tmp = oasysgui.createTabPage(tabs_setting, "Result")
        self.result_id = gui.widgetBox(tmp, "", addSpace=True, orientation="vertical")
        self.result_id.setFixedHeight(self.IMAGE_HEIGHT - 30)
        self.result_id.setFixedWidth(self.IMAGE_WIDTH - 20)

        tmp = oasysgui.createTabPage(tabs_setting, "Interpolation")
        self.interpolation_id = gui.widgetBox(tmp, "", addSpace=True, orientation="vertical")
        self.interpolation_id.setFixedHeight(self.IMAGE_HEIGHT - 30)
        self.interpolation_id.setFixedWidth(self.IMAGE_WIDTH - 20)

        tmp = oasysgui.createTabPage(tabs_setting, "Triangulation")
        self.triangulation_id = gui.widgetBox(tmp, "", addSpace=True, orientation="vertical")
        self.triangulation_id.setFixedHeight(self.IMAGE_HEIGHT - 30)
        self.triangulation_id.setFixedWidth(self.IMAGE_WIDTH - 20)

        tmp = oasysgui.createTabPage(tabs_setting, "Raw Data")
        self.rawdata_id = gui.widgetBox(tmp, "", addSpace=True, orientation="vertical")
        self.rawdata_id.setFixedHeight(self.IMAGE_HEIGHT - 30)
        self.rawdata_id.setFixedWidth(self.IMAGE_WIDTH - 20)

        tmp = oasysgui.createTabPage(tabs_setting, "1D profile")
        self.profile1D_id = gui.widgetBox(tmp, "", addSpace=True, orientation="vertical")
        self.profile1D_id.setFixedHeight(self.IMAGE_HEIGHT - 30)
        self.profile1D_id.setFixedWidth(self.IMAGE_WIDTH - 20)

        tmp = oasysgui.createTabPage(tabs_setting, "1D slope")
        self.slope1D_id = gui.widgetBox(tmp, "", addSpace=True, orientation="vertical")
        self.slope1D_id.setFixedHeight(self.IMAGE_HEIGHT - 30)
        self.slope1D_id.setFixedWidth(self.IMAGE_WIDTH - 20)

        tmp = oasysgui.createTabPage(tabs_setting, "Output")
        self.info_id = oasysgui.textArea(height=self.IMAGE_HEIGHT - 35)
        info_box = oasysgui.widgetBox(tmp, "", addSpace=True, orientation="horizontal", height=self.IMAGE_HEIGHT - 20, width=self.IMAGE_WIDTH - 20)
        info_box.layout().addWidget(self.info_id)

    def set_input_file(self, filename):
        self.le_beam_file_name.setText(filename)

    def selectFile(self):
        filename = oasysgui.selectFileFromDialog(self, previous_file_path=self.file_in, message="Open FEA File", start_directory=".", file_extension_filter="*.*")
        self.le_beam_file_name.setText(filename)
        self.set_file_out()

    def load_raw_data(self):
        self.fea_file_object = FEA_File()
        self.fea_file_object.set_filename(self.file_in)

        self.fea_file_object.load_multicolumn_file(skiprows=self.file_in_skiprows, file_in_type=self.file_in_type, factorX=self.file_factor_x, factorY=self.file_factor_y, factorZ=self.file_factor_z)

        self.fea_file_object.replicate_raw_data(self.replicate_raw_data_flag)

    def writeStdOut(self, text="", initialize=False):
        cursor = self.info_id.textCursor()
        if initialize:
            self.info_id.setText(text)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)

    def set_file_out(self):
        if self.file_in_type == 2:
            file_out = os.path.splitext(self.file_in)[0] + '_processed.h5'
        else:
            file_out = os.path.splitext(self.file_in)[0] + '.h5'
        if file_out[0:4] == "http":
            file_out = file_out.split("/")[-1]
        self.file_out = file_out

    def calculate(self):
        self.writeStdOut(initialize=True)
        sys.stdout = EmittingStream(textWritten=self.writeStdOut)

        self.load_raw_data()
        self.fea_file_object.triangulate()

        if self.file_in_type == 2:
            self.fea_file_object.interpolate(self.n_axis_0, self.n_axis_1, remove_nan=self.remove_nan)
        else:
            self.fea_file_object.interpolate(self.n_axis_0 + 3, self.n_axis_1 + 3, remove_nan=self.remove_nan)

        if self.fea_file_object.does_interpolated_have_nan():
            self.fea_file_object.remove_borders_in_interpolated_data()

        if self.detrended == 0:
            pass
        elif self.detrended == 1:
            self.fea_file_object.detrend_straight_line(axis=0, fitting_domain_ratio=self.detrended_fit_range)
        elif self.detrended == 2:
            self.fea_file_object.detrend_straight_line(axis=1, fitting_domain_ratio=self.detrended_fit_range)
        elif self.detrended == 3:
            self.fea_file_object.detrend_best_circle(axis=0, fitting_domain_ratio=self.detrended_fit_range)
        elif self.detrended == 4:
            self.fea_file_object.detrend_best_circle(axis=1, fitting_domain_ratio=self.detrended_fit_range)

        if self.reset_height_method == 0:
            pass
        elif self.reset_height_method == 1:
            self.fea_file_object.reset_height_to_minimum()
        elif self.reset_height_method == 2:
            self.fea_file_object.reset_height_to_central_value()

        if self.sigma_flag == 1:
            self.fea_file_object.gaussian_filter(sigma_axis0=self.sigma_axis0, sigma_axis1=self.sigma_axis1)

        self.set_file_out()
        self.fea_file_object.write_h5_surface(filename=self.file_out, invert_axes_names=self.invert_axes_names)

        print("File %s written to disk.\n" % self.file_out)

        self.plot_and_send_results()

    def plot_and_send_results(self):
        if self.invert_axes_names:
            self.plot_data2D(self.fea_file_object.Z_INTERPOLATED, self.fea_file_object.x_interpolated, self.fea_file_object.y_interpolated, self.result_id,
                             title="file: %s, axes names INVERTED from ANSYS" % self.file_in,
                             xtitle="Y [m] (%d pixels, max:%f)" % (self.fea_file_object.x_interpolated.size, self.fea_file_object.x_interpolated.max()),
                             ytitle="X [m] (%d pixels, max:%f)" % (self.fea_file_object.y_interpolated.size, self.fea_file_object.y_interpolated.max()))
        else:
            self.plot_data2D(self.fea_file_object.Z_INTERPOLATED, self.fea_file_object.x_interpolated, self.fea_file_object.y_interpolated, self.result_id,
                             title="file: %s, axes as in ANSYS" % self.file_in,
                             xtitle="X [m] (%d pixels, max:%f)" % (self.fea_file_object.x_interpolated.size, self.fea_file_object.x_interpolated.max()),
                             ytitle="Y [m] (%d pixels, max:%f)" % (self.fea_file_object.y_interpolated.size, self.fea_file_object.y_interpolated.max()))

        slp = slopes(self.fea_file_object.Z_INTERPOLATED, self.fea_file_object.x_interpolated, self.fea_file_object.y_interpolated, silent=0, return_only_rms=0)

        print("\n\n\n**** heights: ****")
        print("Heigh error StDev: %g um" % (1e6 * self.fea_file_object.Z_INTERPOLATED.std()))
        print("*****************")

        if self.file_in_type != 2:
            # interpolation plot
            try:
                self.interpolation_id.layout().removeItem(self.interpolation_id.layout().itemAt(1))
                self.interpolation_id.layout().removeItem(self.interpolation_id.layout().itemAt(0))
            except Exception:
                pass

            f = self.fea_file_object.plot_interpolated(show=0)
            figure_canvas = FigureCanvasQTAgg(f)
            toolbar = NavigationToolbar(figure_canvas, self)

            self.interpolation_id.layout().addWidget(toolbar)
            self.interpolation_id.layout().addWidget(figure_canvas)

            # triangulation plot
            try:
                self.triangulation_id.layout().removeItem(self.triangulation_id.layout().itemAt(1))
                self.triangulation_id.layout().removeItem(self.triangulation_id.layout().itemAt(0))
            except Exception:
                pass

            f = self.fea_file_object.plot_triangulation(show=0)
            figure_canvas = FigureCanvasQTAgg(f)
            toolbar = NavigationToolbar(figure_canvas, self)

            self.triangulation_id.layout().addWidget(toolbar)
            self.triangulation_id.layout().addWidget(figure_canvas)

        if self.display_raw_data:
            try:
                self.rawdata_id.layout().removeItem(self.rawdata_id.layout().itemAt(1))
                self.rawdata_id.layout().removeItem(self.rawdata_id.layout().itemAt(0))
            except Exception:
                pass

            xs, ys, zs = self.fea_file_object.get_deformed()
            xs *= 1e3
            ys *= 1e3
            zs *= 1e6

            fig = Figure()
            self.axis = fig.add_subplot(111, projection='3d')

            for m, zlow, zhigh in [('o', zs.min(), zs.max())]:
                self.axis.scatter(xs, ys, zs, marker=m)

            self.axis.set_xlabel('X [mm]')
            self.axis.set_ylabel('Y [mm]')
            self.axis.set_zlabel('Z [um]')

            figure_canvas = FigureCanvasQTAgg(fig)
            toolbar = NavigationToolbar(figure_canvas, self)

            self.rawdata_id.layout().addWidget(toolbar)
            self.rawdata_id.layout().addWidget(figure_canvas)

            try:
                self.axis.mouse_init()
            except Exception:
                pass

        mesh = self.fea_file_object.Z_INTERPOLATED
        x = self.fea_file_object.x_interpolated
        y = self.fea_file_object.y_interpolated

        if self.extract_profile1D == 0:
            abscissas = x
            perp_abscissas = y
            index0 = numpy.argwhere(perp_abscissas >= self.coordinate_profile1D)
            try:
                index0 = index0[0][0]
            except Exception:
                index0 = -1
            profile1D = mesh[:, index0]
            slope1D = numpy.gradient(profile1D, abscissas)
            profile1D_std = profile1D.std()
            slope1D_std = slope1D.std()
            if self.invert_axes_names:
                title = "profile at X[%d] = %g; StDev = %g um" % (index0, perp_abscissas[index0], 1e6 * profile1D_std)
                titleS = "slopes at X[%d] = %g; StDev = %g urad" % (index0, perp_abscissas[index0], 1e6 * slope1D_std)
                xtitle = "Y [m] "
            else:
                title = "profile at Y[%d] = %g; StDev = %g um" % (index0, perp_abscissas[index0], 1e6 * profile1D_std)
                titleS = "slopes at Y[%d] = %g; StDev = %g urad" % (index0, perp_abscissas[index0], 1e6 * slope1D_std)
                xtitle = "X [m] "
            self.plot_data1D(abscissas, 1e6 * profile1D, self.profile1D_id, title=title, xtitle=xtitle, ytitle="Z [um] ")
            self.plot_data1D(abscissas, 1e6 * slope1D, self.slope1D_id, title=titleS, xtitle=xtitle, ytitle="Z' [urad]")
        else:
            abscissas = y
            perp_abscissas = x
            index0 = numpy.argwhere(perp_abscissas >= self.coordinate_profile1D)
            try:
                index0 = index0[0][0]
            except Exception:
                index0 = -1
            profile1D = mesh[index0, :]
            slope1D = numpy.gradient(profile1D, abscissas)
            profile1D_std = profile1D.std()
            slope1D_std = slope1D.std()
            if self.invert_axes_names:
                title = "profile at Y[%d] = %g; StDev = %g um" % (index0, perp_abscissas[index0], 1e6 * profile1D_std)
                titleS = "slopes at Y[%d] = %g; StDev = %g urad" % (index0, perp_abscissas[index0], 1e6 * slope1D_std)
                xtitle = "X [m] "
            else:
                title = "profile at X[%d] = %g; StDev = %g um" % (index0, perp_abscissas[index0], 1e6 * profile1D_std)
                titleS = "slopes at X[%d] = %g; StDev = %g urad" % (index0, perp_abscissas[index0], 1e6 * slope1D_std)
                xtitle = "Y [m] "
            self.plot_data1D(abscissas, 1e6 * profile1D, self.profile1D_id, title=title, xtitle=xtitle, ytitle="Z [um] ")
            self.plot_data1D(abscissas, 1e6 * slope1D, self.slope1D_id, title=titleS, xtitle=xtitle, ytitle="Z' [urad]")

        if self.invert_axes_names:
            self.Outputs.SurfaceData.send(OasysSurfaceData(xx=self.fea_file_object.y_interpolated,
                                                           yy=self.fea_file_object.x_interpolated,
                                                           zz=self.fea_file_object.Z_INTERPOLATED,
                                                           surface_data_file=self.file_out))
        else:
            self.Outputs.SurfaceData.send(OasysSurfaceData(xx=self.fea_file_object.x_interpolated,
                                                           yy=self.fea_file_object.y_interpolated,
                                                           zz=self.fea_file_object.Z_INTERPOLATED.T,
                                                           surface_data_file=self.file_out))

        dabam_profile = numpy.zeros((profile1D.size, 2))
        dabam_profile[:, 0] = abscissas
        dabam_profile[:, 1] = profile1D
        self.Outputs.DABAM1DProfile.send(dabam_profile)

    def plot_data2D(self, data2D, dataX, dataY, tabs_canvas_index, title="title", xtitle="X", ytitle="Y"):
        try:
            # remove first item if exists
            item = tabs_canvas_index.layout().itemAt(0)
            if item is not None:
                tabs_canvas_index.layout().removeItem(item)
        except Exception:
            pass

        origin = (dataX[0], dataY[0])
        scale = (dataX[1] - dataX[0], dataY[1] - dataY[0])

        colormap = {"name": "temperature", "normalization": "linear",
                    "autoscale": True, "vmin": 0, "vmax": 0, "colors": 256}

        tmp = Plot2D()
        tmp.resetZoom()
        tmp.setXAxisAutoScale(True)
        tmp.setYAxisAutoScale(True)
        tmp.setGraphGrid(False)
        tmp.setKeepDataAspectRatio(True)
        try:
            tmp.yAxisInvertedAction.setVisible(False)
        except Exception:
            pass
        tmp.setXAxisLogarithmic(False)
        tmp.setYAxisLogarithmic(False)
        try:
            tmp.getMaskAction().setVisible(False)
            tmp.getRoiAction().setVisible(False)
            tmp.getColormapAction().setVisible(True)
        except Exception:
            pass
        tmp.setKeepDataAspectRatio(False)
        tmp.addImage(data2D.T, legend="1", scale=scale, origin=origin, colormap=colormap, replace=True)
        tmp.setActiveImage("1")
        tmp.setGraphXLabel(xtitle)
        tmp.setGraphYLabel(ytitle)
        tmp.setGraphTitle(title)

        tabs_canvas_index.layout().addWidget(tmp)

    def plot_data1D(self, dataX, dataY, tabs_canvas_index, title="", xtitle="", ytitle=""):
        try:
            item = tabs_canvas_index.layout().itemAt(0)
            if item is not None:
                tabs_canvas_index.layout().removeItem(item)
        except Exception:
            pass

        tmp = oasysgui.plotWindow()
        tmp.addCurve(dataX, dataY)
        tmp.resetZoom()
        tmp.setXAxisAutoScale(True)
        tmp.setYAxisAutoScale(True)
        tmp.setGraphGrid(False)
        tmp.setXAxisLogarithmic(False)
        tmp.setYAxisLogarithmic(False)
        tmp.setGraphXLabel(xtitle)
        tmp.setGraphYLabel(ytitle)
        tmp.setGraphTitle(title)

        tabs_canvas_index.layout().addWidget(tmp)


if __name__ == "__main__":
    a = QApplication(sys.argv)
    ow = FiniteElementReader()
    ow.set_input_file("https://raw.githubusercontent.com/srio/dabam2d/main/data/dabam2d-0001.h5")
    ow.file_in_type = 2
    ow.n_axis_0 = 0
    ow.n_axis_1 = 0
    ow.invert_axes_names = 0
    ow.extract_profile1D = 1

    ow.show()
    a.exec()