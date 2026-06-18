from AnyQt.QtWidgets import QWidget, QVBoxLayout
import copy
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input, Output

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import MessageDialog, Styles
from oasys2.widget.widget import OWWidget

from barc4beams import Beam
from barc4beams.viz import plot_caustic
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


COLOR_MAPS = ["viridis", "plasma", "turbo", "magma", "terrain"]


class OWBeamCaustic(OWWidget):
    name = "Beam Caustic"
    description = "Compute and plot a barc4beams caustic"
    icon = "icons/signal-stream.png"
    priority = 3
    keywords = ["barc", "barc4beams", "beam", "caustic", "plot"]

    want_main_area = 1

    class Inputs:
        shadow_data = Input("Shadow Data", ShadowData, default=True, auto_summary=False)

    class Outputs:
        beam = Output("BARC Beam", Beam, default=True, auto_summary=False)

    which = Setting(2)
    n_points = Setting(501)
    start = Setting(-0.5)
    finish = Setting(0.5)
    aspect_ratio = Setting(False)
    color = Setting(5)
    use_z_range = Setting(False)
    z_range_min = Setting(-0.5)
    z_range_max = Setting(0.5)
    use_xy_range = Setting(False)
    xy_range_min = Setting(-100.0)
    xy_range_max = Setting(100.0)
    bins = Setting(0)
    top_stat = Setting(0)

    def __init__(self):
        super().__init__()

        self._beam = None
        self._shadow_data = None
        self._canvases = []
        self._figures = []

        button_box = oasysgui.widgetBox(
            self.controlArea,
            "",
            addSpace=False,
            orientation="horizontal",
            width=390,
        )
        button = gui.button(button_box, self, "Plot Caustic", callback=self.plot_results)
        button.setStyleSheet(Styles.button_blue)

        caustic_box = oasysgui.widgetBox(
            self.controlArea,
            "Caustic",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        oasysgui.lineEdit(
            caustic_box,
            self,
            "n_points",
            "Number of planes",
            labelWidth=180,
            valueType=int,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            caustic_box,
            self,
            "start",
            "Start [m]",
            labelWidth=180,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            caustic_box,
            self,
            "finish",
            "Finish [m]",
            labelWidth=180,
            valueType=float,
            orientation="horizontal",
        )

        plot_box = oasysgui.widgetBox(
            self.controlArea,
            "Plot",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        gui.comboBox(
            plot_box,
            self,
            "which",
            label="Plane",
            labelWidth=180,
            items=["X", "Y", "Both"],
            sendSelectedValue=False,
            orientation="horizontal",
        )
        gui.checkBox(plot_box, self, "aspect_ratio", "Aspect ratio")
        gui.comboBox(
            plot_box,
            self,
            "color",
            label="Color",
            labelWidth=180,
            orientation="horizontal",
            items=COLOR_MAPS,
            sendSelectedValue=False,
        )
        oasysgui.lineEdit(
            plot_box,
            self,
            "bins",
            "Number of Bins (0 = auto)",
            labelWidth=180,
            valueType=int,
            orientation="horizontal",
        )
        gui.comboBox(
            plot_box,
            self,
            "top_stat",
            label="Top panel",
            labelWidth=180,
            items=["None", "FWHM", "STD"],
            sendSelectedValue=False,
            orientation="horizontal",
        )

        range_box = oasysgui.widgetBox(
            self.controlArea,
            "Ranges",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        gui.checkBox(range_box, self, "use_z_range", "Set Z range", callback=self._update_visibility)
        self.z_range_box = oasysgui.widgetBox(range_box, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(
            self.z_range_box,
            self,
            "z_range_min",
            "Z min [m]",
            labelWidth=180,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.z_range_box,
            self,
            "z_range_max",
            "Z max [m]",
            labelWidth=180,
            valueType=float,
            orientation="horizontal",
        )

        gui.checkBox(range_box, self, "use_xy_range", "Set X/Y range", callback=self._update_visibility)
        self.xy_range_box = oasysgui.widgetBox(range_box, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(
            self.xy_range_box,
            self,
            "xy_range_min",
            "X/Y min [um]",
            labelWidth=180,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.xy_range_box,
            self,
            "xy_range_max",
            "X/Y max [um]",
            labelWidth=180,
            valueType=float,
            orientation="horizontal",
        )

        self.plot_tabs = oasysgui.tabWidget(self.mainArea)

        gui.rubber(self.controlArea)
        self._update_visibility()

    @Inputs.shadow_data
    def set_shadow_data(self, shadow_data):
        self._shadow_data = shadow_data

        if shadow_data is not None:
            self.plot_results()

    def plot_results(self):
        self.setStatusMessage("")

        try:
            if self._shadow_data is None:
                raise ValueError("No Shadow Data input received.")

            self._beam = self._beam_from_shadow_data(self._shadow_data)

            n_points = int(self.n_points)
            if n_points < 2:
                raise ValueError("Number of planes must be at least 2.")

            if self.start >= self.finish:
                raise ValueError("Start must be smaller than finish.")

            caustic = self._beam.caustic(
                n_points=n_points,
                start=float(self.start),
                finish=float(self.finish),
            )

            self._clear_plots()

            which = self._which()
            result = plot_caustic(
                caustic,
                which=which,
                aspect_ratio=bool(self.aspect_ratio),
                color=self._color_index(),
                z_range=self._range_or_none(self.use_z_range, self.z_range_min, self.z_range_max),
                xy_range=self._range_or_none(self.use_xy_range, self.xy_range_min, self.xy_range_max),
                bins=self._bins_or_none(),
                top_stat=self._top_stat_or_none(),
                plot=False,
            )

            if which == "both":
                fig_x, _ = result[0]
                fig_y, _ = result[1]
                self._add_figure_tab("Caustic X", fig_x)
                self._add_figure_tab("Caustic Y", fig_y)
            else:
                fig, _ = result
                self._add_figure_tab(f"Caustic {which.upper()}", fig)

            self.Outputs.beam.send(self._beam)
            self.setStatusMessage("Caustic plot updated.")
        except Exception as exception:
            self._beam = None
            self.Outputs.beam.send(None)
            self.setStatusMessage(str(exception))
            MessageDialog.message(
                parent=self,
                title="Caustic Error",
                type="critical",
                message=str(exception),
            )

    def _add_figure_tab(self, title, figure):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        canvas = FigureCanvas(figure)
        toolbar = NavigationToolbar(canvas, tab)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        self.plot_tabs.addTab(tab, title)
        self._canvases.append(canvas)
        self._figures.append(figure)
        canvas.draw()

    def _clear_plots(self):
        for figure in self._figures:
            plt.close(figure)

        self._canvases = []
        self._figures = []

        while self.plot_tabs.count() > 0:
            widget = self.plot_tabs.widget(0)
            self.plot_tabs.removeTab(0)
            widget.deleteLater()

    def _update_visibility(self):
        self.z_range_box.setVisible(bool(self.use_z_range))
        self.xy_range_box.setVisible(bool(self.use_xy_range))

    def _which(self):
        return ["x", "y", "both"][self.which]

    def _bins_or_none(self):
        bins = int(self.bins)
        return None if bins <= 0 else bins

    def _top_stat_or_none(self):
        if self.top_stat == 1:
            return "fwhm"
        if self.top_stat == 2:
            return "std"
        return None

    def _color_index(self):
        color = int(self.color)

        if color < 0:
            color = 0
        elif color >= len(COLOR_MAPS):
            color = len(COLOR_MAPS) - 1

        self.color = color
        return color + 1

    @staticmethod
    def _beam_from_shadow_data(shadow_data):
        if shadow_data.beam is None:
            raise ValueError("Shadow Data does not contain a beam.")

        shadow_beam = OWBeamCaustic._copy_shadow_beam(shadow_data.beam)
        return Beam(shadow_beam, code="s4")

    @staticmethod
    def _copy_shadow_beam(shadow_beam):
        if hasattr(shadow_beam, "duplicate"):
            return shadow_beam.duplicate()

        return copy.deepcopy(shadow_beam)

    @staticmethod
    def _range_or_none(enabled, minimum, maximum):
        if not enabled:
            return None

        if minimum >= maximum:
            raise ValueError("Range minimum must be smaller than range maximum.")

        return (float(minimum), float(maximum))


add_widget_parameters_to_module(__name__)
