import os, sys
import numpy

from syned.storage_ring.light_source import LightSource, ElectronBeam
from syned.beamline.beamline import Beamline

from AnyQt.QtGui import QPalette, QColor, QFont, QTextCursor
from AnyQt.QtWidgets import QApplication, QMessageBox
from AnyQt.QtCore import QRect

from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Output

from oasys2.widget.widget import OWWidget
from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence

from oasys2.widget.widget import OWAction
from oasys2.widget.gui import MessageDialog, ConfirmDialog

import orangecanvas.resources as resources

import at  # accelerator toolbox

from oasys2.widget.util.widget_util import EmittingStream

VERTICAL = 1
HORIZONTAL = 2
BOTH = 3

lattice_file = os.path.join(resources.package_dirname("orangecontrib.esrf.syned.data"), 'S28F_all_BM.mat')
AT_LATTICE = at.load_lattice(lattice_file)

def get_electron_beam_parameters_from_at(r0=AT_LATTICE, id_number=1, s_locs=None, npoints=10, verbose=False):
    id = f'ID{id_number:02d}'
    IDind = r0.get_uint32_index(id)
    s0 = r0.get_s_pos(IDind)[0]

    cell_length = (r0.get_s_pos(at.End) / 32)[0]

    if s_locs is None:
        s_locs = numpy.linspace(s0, s0 + cell_length, npoints)
    else:
        s_locs = numpy.array(s_locs)

    Circumference = r0.get_s_pos(at.End)
    npoints = s_locs.shape[0]

    r = r0.sbreak(break_s=list(s_locs))
    s_ind = r.get_uint32_index('sbreak')

    if verbose:
        print('get lattice parameters')
    r.enable_6d()
    p0 = r.envelope_parameters()

    epsilonX = p0.emittances[0]
    epsilonY = 10 * 1e-12
    delta = p0.sigma_e

    if verbose:
        print('get orbit, dispersion, beta functions')
    _, _, l = r.linopt6(refpts=s_ind)

    if verbose:
        print('get geometry')
    geom, _ = r.get_geometry(refpts=s_ind)

    data = []

    def _get_cell_for_s(i, s):
        s1 = s - s0
        alpha = l[i].alpha
        alphaX, alphaY = alpha[0], alpha[1]
        beta = l[i].beta
        betaX, betaY = beta[0], beta[1]
        gammaX = (1.0 + alphaX ** 2) / betaX
        gammaY = (1.0 + alphaY ** 2) / betaY
        eta = l[i].dispersion
        etaX, etaXp, etaY, etaYp = eta[0], eta[1], eta[2], eta[3]

        xx = betaX * epsilonX + (etaX * delta) ** 2
        yy = betaY * epsilonY + (etaY * delta) ** 2
        xxp = -alphaX * epsilonX + etaX * etaXp * delta ** 2
        yyp = -alphaY * epsilonY + etaY * etaYp * delta ** 2
        xpxp = gammaX * epsilonX + (etaXp * delta) ** 2
        ypyp = gammaY * epsilonY + (etaYp * delta) ** 2

        lab_x = geom[i].x
        lab_y = geom[i].y
        angle = geom[i].angle

        return [s1, s, lab_x, lab_y, angle, alphaX, alphaY, betaX, betaY, gammaX, gammaY, etaX, etaY, etaXp, etaYp,
                xx, yy, xxp, yyp, xpxp, ypyp, numpy.sqrt(xx), numpy.sqrt(yy), numpy.sqrt(xpxp), numpy.sqrt(ypyp),
                numpy.sqrt(xx * xpxp), numpy.sqrt(yy * ypyp)]

    for i in range(0, npoints):
        tmp = _get_cell_for_s(i, s_locs[i])
        data.append(tmp)

    labels = ['s0', 's', 'lab_x', 'lab_y', 'angle', 'alphaX', 'alphaY', 'betaX', 'betaY', 'gammaX', 'gammaY', 'etaX', 'etaY', 'etaXp', 'etaYp',
              'xx', 'yy', 'xxp', 'yyp', 'xpxp', 'ypyp', 'sigma x', 'sigma y', "sigma x'", "sigma y'", "<x * x'>", "<y * y'>"]

    return numpy.array(data), epsilonX, epsilonY, labels, s0

class OWEBSCELL(OWWidget):

    name = "ESRF-EBS Cell Parameters"
    description = "Syned: ESRF-EBS Cell Parameters"
    icon = "icons/at_ebs.png"
    priority = 1.2

    maintainer = "Manuel Sanchez del Rio"
    maintainer_email = "srio(@at@)esrf.eu"
    category = "ESRF-EBS Syned Tools"
    keywords = ["data", "file", "load", "read"]

    class Outputs:
        SynedData = Output("SynedData", Beamline)

    want_main_area = 1

    MAX_WIDTH = 1320
    MAX_HEIGHT = 700
    IMAGE_WIDTH = 860
    IMAGE_HEIGHT = 645
    CONTROL_AREA_WIDTH = 450
    TABS_AREA_HEIGHT = 625

    type_of_properties = Setting(0)
    number_of_points = Setting(250)
    ebs_id_index = Setting(0)
    shift_from_center_of_straight_section = Setting(0.0)

    data = None
    values_at_undulator_center = None

    def __init__(self):
        super().__init__()

        button_box = oasysgui.widgetBox(self.controlArea, "", addSpace=False, orientation="horizontal")

        button = gui.button(button_box, self, "Calculate/Refresh", callback=self.refresh)
        font = QFont(button.font())
        font.setBold(True)
        button.setFont(font)
        palette = QPalette(button.palette())
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("darkblue"))
        button.setPalette(palette)
        button.setFixedHeight(45)

        gui.separator(self.controlArea)

        geom = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(QRect(round(geom.width() * 0.05),
                               round(geom.height() * 0.05),
                               round(min(geom.width() * 0.98, self.MAX_WIDTH)),
                               round(min(geom.height() * 0.95, self.MAX_HEIGHT))))

        self.setMaximumHeight(self.geometry().height())
        self.setMaximumWidth(self.geometry().width())

        self.controlArea.setFixedWidth(self.CONTROL_AREA_WIDTH)

        self.tabs_setting = oasysgui.tabWidget(self.controlArea)
        self.tabs_setting.setFixedHeight(self.TABS_AREA_HEIGHT)
        self.tabs_setting.setFixedWidth(self.CONTROL_AREA_WIDTH - 5)

        self.tab_sou = oasysgui.createTabPage(self.tabs_setting, "EBS Cell Setting")

        self.electron_beam_box = oasysgui.widgetBox(self.tab_sou, "Storage Ring Parameters", addSpace=False, orientation="vertical")

        gui.comboBox(self.electron_beam_box, self, "type_of_properties", label="accelerator toolbox file", labelWidth=250,
                     items=["EBS (S28F 140pm H, 10pm V)"], callback=self.update_cell_file,
                     sendSelectedValue=False, orientation="horizontal")

        gui.comboBox(self.electron_beam_box, self, "ebs_id_index", label="Load parameters from ID cell:", labelWidth=350,
                     items=self.get_id_list(), callback=self.set_id, sendSelectedValue=False, orientation="horizontal")

        oasysgui.lineEdit(self.electron_beam_box, self, "number_of_points", "number of points in a cell (for plots)",
                          labelWidth=360, valueType=int, orientation="horizontal", callback=self.refresh)

        oasysgui.lineEdit(self.electron_beam_box, self, "shift_from_center_of_straight_section", "undulator center from straight section center",
                          labelWidth=360, valueType=float, orientation="horizontal", callback=self.refresh)

        gui.rubber(self.controlArea)
        self.initializeTabs()

    def get_id_list(self):
        return [f"ID{i:02d}" for i in range(1, 33)]

    def titles(self):
        return ["Beta", "Alpha", "Dispersion", "sigma", "sigma'"]

    def xtitles(self):
        return ['s [m]'] * len(self.titles())

    def ytitles(self):
        return ['beta [m]', 'alpha', 'eta', 'sigma [m]', 'sigma prime [rad]']

    def initializeTabs(self):
        self.tabs = oasysgui.tabWidget(self.mainArea)
        self.tab = []
        n_plots = len(self.titles())

        for i in range(n_plots):
            self.tab.append(oasysgui.createTabPage(self.tabs, self.titles()[i]))

        self.tab.append(oasysgui.createTabPage(self.tabs, "Info"))

        for tab in self.tab:
            tab.setFixedHeight(self.IMAGE_HEIGHT)
            tab.setFixedWidth(self.IMAGE_WIDTH)

        self.info_id = oasysgui.textArea(height=self.IMAGE_HEIGHT - 5, width=self.IMAGE_WIDTH - 5)
        profile_box = oasysgui.widgetBox(self.tab[-1], "", addSpace=True, orientation="horizontal", height=self.IMAGE_HEIGHT, width=self.IMAGE_WIDTH - 5)
        profile_box.layout().addWidget(self.info_id)

        self.plot_canvas = [oasysgui.plotWindow(roi=False, control=False, position=True) for _ in range(n_plots)]

        for i in range(n_plots):
            self.plot_canvas[i].setDefaultPlotLines(True)
            # self.plot_canvas[i].setActiveCurveColor(color='blue')
            self.plot_canvas[i].setGraphXLabel(self.xtitles()[i])
            self.plot_canvas[i].setGraphYLabel(self.ytitles()[i])
            self.plot_canvas[i].setGraphTitle(self.titles()[i])
            self.plot_canvas[i].setInteractiveMode(mode='zoom')
            self.tab[i].layout().addWidget(self.plot_canvas[i])

        self.tabs.setCurrentIndex(n_plots)

    def get_id_number(self):
        return self.ebs_id_index + 1

    def update_cell_file(self):
        pass

    def set_id(self):
        pass

    def plot_graph(self, plot_canvas_index, curve_name, x_values, y_values, xtitle="", ytitle="", color='blue', replace=True):
        self.plot_canvas[plot_canvas_index].addCurve(x_values, y_values, curve_name, symbol='', color=color, replace=replace)
        self.plot_canvas[plot_canvas_index].setGraphXLabel(xtitle)
        self.plot_canvas[plot_canvas_index].setGraphYLabel(ytitle)
        self.plot_canvas[plot_canvas_index].replot()

    def update_plots(self):
        INDICES = [[7, 8], [5, 6], [11, 12], [21, 22], [23, 24]]
        colors = ['black', 'red']

        for iplot in range(5):
            indices = INDICES[iplot]
            xtitle = self.xtitles()[iplot]
            ytitle = self.ytitles()[iplot]
            title = self.titles()[iplot]
            labels = [f"{title} X", f"{title} Y"]

            for i, index in enumerate(indices):
                self.plot_canvas[iplot].addCurve(self.data[:, 0], self.data[:, index], labels[i], xlabel=xtitle, ylabel=ytitle, symbol='', color=colors[i])

            self.plot_canvas[iplot].getLegendsDockWidget().setFixedHeight(150)
            self.plot_canvas[iplot].getLegendsDockWidget().setVisible(True)
            self.plot_canvas[iplot].setActiveCurve(labels[0])
            self.plot_canvas[iplot].replot()

    def writeStdOut(self, text):
        cursor = self.info_id.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.info_id.setTextCursor(cursor)
        self.info_id.ensureCursorVisible()

    def refresh(self):
        n_id = self.get_id_number()

        try:
            self.data, epsilonX, epsilonY, labels, s0 = get_electron_beam_parameters_from_at(id_number=n_id, npoints=self.number_of_points, verbose=True)
        except Exception as exception:
            MessageDialog.message(self, str(exception), "Exception occurred in OASYS", "critical")
            return

        self.info_id.setText("")
        sys.stdout = EmittingStream(textWritten=self.writeStdOut)

        print("\n\nValues calculated using the Accelerator Toolbox https://github.com/atcollab/at")
        print(f"with file {lattice_file}\n")
        print(f"\n============== data for cell sector ID{n_id:02d} ================\n")
        print(f"epsilon_x = {epsilonX:.3g} m.rad")
        print(f"epsilon_y = {epsilonY:.3g} m.rad\n\n")

        print(f"============== data at center of the straight section (s={s0:.6f} m)")
        for i, label in enumerate(labels):
            print(f"{label} = {self.data[0, i]:.5g}")

        self.values_at_undulator_center, epsilonX, epsilonY, labels, s0 = get_electron_beam_parameters_from_at(id_number=n_id, s_locs=[s0 + self.shift_from_center_of_straight_section], npoints=1, verbose=True)

        print("\n\n============== data at undulator center at %.3f m from center of the straight section\n" % self.shift_from_center_of_straight_section)
        for i, label in enumerate(labels):
            print(f"{label} = {self.values_at_undulator_center[0, i]:.5g}")

        self.update_plots()

        try:
            self.Outputs.SynedData.send(
                Beamline(light_source=LightSource(
                    name="EBS data",
                    electron_beam=self.get_electron_beam(),
                    magnetic_structure=None)))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e.args[0]), QMessageBox.StandardButton.Ok)

    def get_electron_beam(self):
        return ElectronBeam(
            energy_in_GeV=6.0,
            energy_spread=0.001,
            current=0.2,
            number_of_bunches=0,
            moment_xx=self.values_at_undulator_center[0, 15],
            moment_xxp=self.values_at_undulator_center[0, 17],
            moment_xpxp=self.values_at_undulator_center[0, 19],
            moment_yy=self.values_at_undulator_center[0, 16],
            moment_yyp=self.values_at_undulator_center[0, 18],
            moment_ypyp=self.values_at_undulator_center[0, 20],
        )

    def callResetSettings(self):
        if ConfirmDialog.confirmed(parent=self, message="Confirm Reset of the Fields?"):
            try:
                self.resetSettings()
            except Exception:
                pass

if __name__ == "__main__":
    a = QApplication(sys.argv)
    ow = OWEBSCELL()
    ow.show()
    a.exec()