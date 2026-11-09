import os
import sys
import numpy

from AnyQt.QtCore import QRect, Qt
from AnyQt.QtWidgets import QApplication, QMessageBox, QLabel, QSizePolicy
from AnyQt.QtGui import QTextCursor, QPixmap

from silx.gui.plot import Plot2D

import orangecanvas.resources as resources

from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Output

from oasys2.widget.widget import OWWidget
from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence

from oasys2.widget.util.widget_util import EmittingStream
from oasys2.widget.util.widget_objects import OasysSurfaceData
from oasys2.widget.util.widget_util import write_surface_file

from barc4ro.projected_thickness import proj_thick_2D_crl

from orangecontrib.esrf.util.python_script import PythonScript

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

class OWLensSurface(OWWidget):
    name = "Lens surface creator"
    id = "Lens surface creator"
    description = "Lens surface generator"
    icon = "icons/lens_surface.png"
    author = "M Sanchez del Rio"
    maintainer_email = "srio@esrf.eu"
    priority = 20
    category = ""
    keywords = ["preprocessor", "surface", "lens"]

    class Outputs:
        surface_data = Output("Surface Data", OasysSurfaceData, default=True, auto_summary=False)

    want_main_area = 1
    want_control_area = 1

    MAX_WIDTH = 1320
    MAX_HEIGHT = 700

    IMAGE_WIDTH = 860
    IMAGE_HEIGHT = 645

    CONTROL_AREA_WIDTH = 405
    TABS_AREA_HEIGHT = 650

    # variables
    number_of_curved_surfaces = Setting(2)
    lens_radius = Setting(200e-6)
    surface_shape = Setting(0)
    two_d_lens = Setting(0)
    wall_thickness = Setting(10e-6)
    n_lenses = Setting(1)
    multiplicative_factor = Setting(1.0)
    aperture_shape = Setting(0)
    aperture_dimension_v = Setting(1e-3)
    aperture_dimension_h = Setting(1e-3)
    nx = Setting(101)
    ny = Setting(101)
    semilength_x = Setting(0.001)
    semilength_y = Setting(0.001)
    filename_h5 = Setting("lens.h5")

    usage_path = os.path.join(resources.package_dirname("orangecontrib.esrf.syned.widgets.extension"), "misc", "lens_surface_usage.png")

    def __init__(self):
        super().__init__()

        geom = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(QRect(round(geom.width() * 0.05),
                               round(geom.height() * 0.05),
                               round(min(geom.width() * 0.98, self.MAX_WIDTH)),
                               round(min(geom.height() * 0.95, self.MAX_HEIGHT))))

        self.setMaximumHeight(self.geometry().height())
        self.setMaximumWidth(self.geometry().width())

        gui.separator(self.controlArea)

        tabs_setting = oasysgui.tabWidget(self.controlArea)
        tabs_setting.setFixedHeight(self.TABS_AREA_HEIGHT)
        tabs_setting.setFixedWidth(self.CONTROL_AREA_WIDTH - 5)

        tab_calc = oasysgui.createTabPage(tabs_setting, "Calculate")
        tab_usa = oasysgui.createTabPage(tabs_setting, "Use of the Widget")

        gui.button(tab_calc, self, "Calculate", callback=self.calculate)

        out_calc = oasysgui.widgetBox(tab_calc, "Lens Settings", addSpace=True, orientation="vertical")
        self.draw_lens_settings_box(id=out_calc)
        gui.separator(out_calc)

        out_calc = oasysgui.widgetBox(tab_calc, "Mesh Parameters", addSpace=True, orientation="vertical")

        oasysgui.lineEdit(out_calc, self, "ny", "Points in Y (tangential)", labelWidth=300, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(out_calc, self, "nx", "Points in X (sagittal)", labelWidth=300, valueType=int, orientation="horizontal")
        oasysgui.lineEdit(out_calc, self, "semilength_y", "Half length Y [m]", labelWidth=300, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(out_calc, self, "semilength_x", "Half length X [m]", labelWidth=300, valueType=float, orientation="horizontal")

        gui.separator(out_calc)

        out_file = oasysgui.widgetBox(tab_calc, "Output hdf5 file", addSpace=True, orientation="vertical")

        oasysgui.lineEdit(out_file, self, "filename_h5", "Output filename *.h5", labelWidth=150, valueType=str, orientation="horizontal")

        gui.separator(out_file)

        tab_usa.setStyleSheet("background-color: white;")

        usage_box = oasysgui.widgetBox(tab_usa, "", addSpace=True, orientation="horizontal")

        label = QLabel("")
        label.setAlignment(Qt.AlignCenter)
        label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        if os.path.exists(self.usage_path):
            label.setPixmap(QPixmap(self.usage_path))

        usage_box.layout().addWidget(label)

        gui.rubber(self.controlArea)
        self.initializeTabs()
        self.set_visible()
        self.update_script()
        gui.rubber(self.mainArea)

    def initializeTabs(self):
        self.tabs = oasysgui.tabWidget(self.mainArea)

        self.tab = [oasysgui.createTabPage(self.tabs, "Results"),
                    oasysgui.createTabPage(self.tabs, "Output"),
                    oasysgui.createTabPage(self.tabs, "Script"),
                    ]

        for tab in self.tab:
            tab.setFixedHeight(self.IMAGE_HEIGHT)
            tab.setFixedWidth(self.IMAGE_WIDTH)

        self.profileInfo = oasysgui.textArea()
        profile_box = oasysgui.widgetBox(self.tab[1], "", addSpace=True, orientation="horizontal")
        profile_box.layout().addWidget(self.profileInfo)

        # script widget
        self.python_script = PythonScript()
        self.python_script.code_area.setFixedHeight(400)
        script_box = gui.widgetBox(self.tab[2], "Python script", addSpace=True, orientation="horizontal")
        script_box.layout().addWidget(self.python_script)

        self.tabs.setCurrentIndex(0)

    def draw_lens_settings_box(self, id):

        gui.comboBox(id, self, "surface_shape", label="Lens shape", labelWidth=350,
                     items=["Plane", "Parabolic"], sendSelectedValue=False, orientation="horizontal", callback=self.set_visible)

        oasysgui.lineEdit(id, self, "wall_thickness", "(t_wall) Wall thickness [m]", labelWidth=260, valueType=float, orientation="horizontal")

        self.lens_id = oasysgui.widgetBox(id, orientation="vertical", height=None)

        gui.comboBox(self.lens_id, self, "number_of_curved_surfaces", label="Number of curved surfaces", labelWidth=350,
                     items=["0 (parallel plate)", "1 (plano-concave)", "2 (bi-concave)"], sendSelectedValue=False, orientation="horizontal", callback=self.set_visible)

        oasysgui.lineEdit(self.lens_id, self, "lens_radius", "(R) radius of curvature [m]", labelWidth=260, valueType=float, orientation="horizontal")

        gui.comboBox(self.lens_id, self, "two_d_lens", label="Focusing in", labelWidth=350,
                     items=["2D", "1D (tangential)", "1D (sagittal)"], sendSelectedValue=False, orientation="horizontal")

        gui.comboBox(self.lens_id, self, "aperture_shape", label="Aperture shape", labelWidth=350,
                     items=["Circular", "Rectangular"], sendSelectedValue=False, orientation="horizontal", callback=self.set_visible)

        oasysgui.lineEdit(self.lens_id, self, "aperture_dimension_v", "Aperture V (height/diameter) [m]", labelWidth=260, valueType=float, orientation="horizontal")

        self.lens_width_id = oasysgui.widgetBox(self.lens_id, orientation="vertical", height=None)
        oasysgui.lineEdit(self.lens_width_id, self, "aperture_dimension_h", "Aperture H (width) [m]", labelWidth=260, valueType=float, orientation="horizontal")

        oasysgui.lineEdit(self.lens_id, self, "n_lenses", "Number of lenses", labelWidth=300, valueType=int, orientation="horizontal")

        oasysgui.lineEdit(id, self, "multiplicative_factor", "Multiplicative factor for z (default=1.0)", labelWidth=300, valueType=float, orientation="horizontal")

    def set_visible(self):
        self.lens_id.setVisible(self.surface_shape == 1)
        self.lens_width_id.setVisible(self.aperture_shape == 1)

    def check_fields(self):
        self.nx = congruence.checkStrictlyPositiveNumber(self.nx, "Points X")
        self.ny = congruence.checkStrictlyPositiveNumber(self.ny, "Points Y")
        if self.nx < 2 or self.ny < 2: raise Exception("Points X and Points Y must be at least 2")
        self.semilength_x = congruence.checkStrictlyPositiveNumber(self.semilength_x, "Half length X")
        self.semilength_y = congruence.checkStrictlyPositiveNumber(self.semilength_y, "Half length Y")

    def writeStdOut(self, text="", initialize=False):
        cursor = self.profileInfo.textCursor()
        if initialize:
            self.profileInfo.setText(text)
        else:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertText(text)

    def calculate(self):
        self.writeStdOut(initialize=True)
        old_stdout = sys.stdout
        sys.stdout = EmittingStream(textWritten=self.writeStdOut)
        try:
            self._calculate()
        except Exception as exception:
            QMessageBox.critical(self, "Error", str(exception), QMessageBox.StandardButton.Ok)
            if self.IS_DEVELOP: raise exception
        finally:
            sys.stdout = old_stdout

    def _calculate(self):
        self.check_fields()
        self.update_script()

        x = numpy.linspace(-self.semilength_x, self.semilength_x, self.nx)
        y = numpy.linspace(-self.semilength_y, self.semilength_y, self.ny)

        # Z is kept internally as Z[ix, iy], shape (nx, ny) (shadow4 convention);
        # the h5 file and OasysSurfaceData use the transposed array, shape (ny, nx).
        if self.surface_shape == 0:  # plane
            Z = numpy.ones((self.nx, self.ny)) * self.wall_thickness
            title = "Cumulated lens profile [m]"

        else:  # parabolic
            title = "Cumulated lens profile [m] R:%6.3f $\\mu$m" % (1e6 * self.lens_radius)

            foc_plane, shape, apert_h, apert_v, r_min, n, aperture = self.get_barc_inputs()
            print("barc4ro.proj_thick_2D_crl inputs: foc_plane=%d (1=horizontal, 2=vertical, 3=both), "
                  "shape=%d (1=parabolic), apert_h=%g m, apert_v=%g m, r_min=%g m, n=%d, aperture=%s" %
                  (foc_plane, shape, apert_h, apert_v, r_min, n, aperture))

            _, _, Z = proj_thick_2D_crl(foc_plane, shape, apert_h, apert_v, r_min, n,
                                        _wall_thick=self.wall_thickness, _aperture=aperture,
                                        _nx=self.nx, _ny=self.ny, _axis_x=x, _axis_y=y,
                                        isdgr=False, project=True)
            Z = Z.T * self.n_lenses  # barc4ro returns Z[iy, ix], shape (ny, nx): bring it to the internal (nx, ny)

        Z = Z * self.multiplicative_factor

        write_surface_file(Z.T, x, y, self.filename_h5, overwrite=True)
        print("\nHDF5 file %s written to disk." % self.filename_h5)

        self.plot_data2D(Z, x, y, self.tab[0],
                         title=title,
                         xtitle="x (sagittal) [m] (%d pixels)" % x.size,
                         ytitle="y (tangential) [m] (%d pixels)" % y.size)

        self.Outputs.surface_data.send(
            OasysSurfaceData(xx=x, yy=y, zz=Z.T, surface_data_file=self.filename_h5))

    def get_barc_inputs(self):
        """Inputs for barc4ro.projected_thickness.proj_thick_2D_crl (parabolic lens)."""
        if self.number_of_curved_surfaces == 0:  # parallel plate: treated as a very large parabola
            foc_plane, r_min, n = 3, 1e18, 1
        else:
            foc_plane = {0: 3, 1: 2, 2: 1}[self.two_d_lens]  # 2D: both; 1D tangential: vertical; 1D sagittal: horizontal
            r_min = self.lens_radius
            n = 1 if self.number_of_curved_surfaces == 1 else 2  # plano-concave / bi-concave
        shape = 1  # parabolic
        if self.aperture_shape == 0:  # circular (diameter = aperture V)
            aperture, apert_h, apert_v = "c", self.aperture_dimension_v, self.aperture_dimension_v
        else:                         # rectangular
            aperture, apert_h, apert_v = "r", self.aperture_dimension_h, self.aperture_dimension_v
        return foc_plane, shape, apert_h, apert_v, r_min, n, aperture

    def update_script(self):
        # Python script reproducing the calculation done in _calculate()
        script = """
import numpy
from oasys2.widget.util.widget_util import write_surface_file
from srxraylib.plot.gol import plot_image
"""
        if self.surface_shape == 1:
            script += """from barc4ro.projected_thickness import proj_thick_2D_crl
"""
        script += """
#
# inputs
#
nx, ny                = %d, %d
semilength_x          = %r # m
semilength_y          = %r # m
wall_thickness        = %r # m
multiplicative_factor = %r
filename_h5           = %r
""" % (self.nx, self.ny, float(self.semilength_x), float(self.semilength_y),
       float(self.wall_thickness), float(self.multiplicative_factor), self.filename_h5)

        script += """
x = numpy.linspace(-semilength_x, semilength_x, nx)
y = numpy.linspace(-semilength_y, semilength_y, ny)

# Z is kept as Z[ix, iy], shape (nx, ny) (shadow4 convention);
# the h5 file uses the transposed array, shape (ny, nx).
"""
        if self.surface_shape == 0:  # plane
            script += """Z = numpy.ones((nx, ny)) * wall_thickness
title = "Cumulated lens profile [m]"
"""
        else:  # parabolic
            foc_plane, shape, apert_h, apert_v, r_min, n, aperture = self.get_barc_inputs()
            script += """
# projected thickness of one parabolic lens (barc4ro)
_, _, Z = proj_thick_2D_crl(
    %d,      # _foc_plane: plane of focusing: 1=horizontal (sagittal), 2=vertical (tangential), 3=both
    %d,      # _shape: 1=parabolic
    %r, # _apert_h: horizontal aperture [m]
    %r, # _apert_v: vertical aperture [m]
    %r, # _r_min: radius at the parabola tip [m] (1e18 for a parallel plate)
    %d,      # _n: number of curved surfaces ("holes"): 1=plano-concave, 2=bi-concave
    _wall_thick=wall_thickness,
    _aperture=%r, # 'c'=circular, 'r'=rectangular
    _nx=nx, _ny=ny, _axis_x=x, _axis_y=y,
    isdgr=False, project=True)

n_lenses = %d
Z = Z.T * n_lenses  # barc4ro returns Z[iy, ix], shape (ny, nx)
title = "Cumulated lens profile [m] R:%%6.3f $\\\\mu$m" %% (1e6 * %r)
""" % (foc_plane, shape, float(apert_h), float(apert_v), float(r_min), n, aperture, self.n_lenses,
       float(self.lens_radius))

        script += """
Z = Z * multiplicative_factor

write_surface_file(Z.T, x, y, filename_h5, overwrite=True)
print("HDF5 file %s written to disk." % filename_h5)

plot_image(Z, x, y, title=title, xtitle="x (sagittal) [m]", ytitle="y (tangential) [m]", aspect='auto')
"""
        self.python_script.set_code(script)

    def plot_data2D(self, data2D, dataX, dataY, canvas_widget_id, title="title", xtitle="X", ytitle="Y"):
        # delete previous plot(s): removeItem() alone leaves the widget alive and visible
        layout = canvas_widget_id.layout()
        while layout.count() > 0:
            old = layout.takeAt(0).widget()
            if old is not None:
                old.setParent(None)
                old.deleteLater()

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
        tmp.yAxisInvertedAction.setVisible(False)
        tmp.setXAxisLogarithmic(False)
        tmp.setYAxisLogarithmic(False)
        tmp.getMaskAction().setVisible(False)
        tmp.getRoiAction().setVisible(False)
        tmp.getColormapAction().setVisible(True)
        tmp.setKeepDataAspectRatio(False)
        tmp.addImage(data2D.T, legend="1", scale=scale, origin=origin, colormap=colormap, replace=True)
        tmp.setActiveImage("1")
        tmp.setGraphXLabel(xtitle)
        tmp.setGraphYLabel(ytitle)
        tmp.setGraphTitle(title)

        canvas_widget_id.layout().addWidget(tmp)

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = OWLensSurface()
    w.show()
    app.exec()
    w.saveSettings()
