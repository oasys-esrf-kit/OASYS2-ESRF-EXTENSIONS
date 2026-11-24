from AnyQt.QtGui import QFontDatabase
from AnyQt.QtWidgets import QWidget, QVBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import MessageDialog, Styles
from oasys2.widget.widget import OWWidget

from barc4shadow.beamline import layout_information, s4_beamline_to_layout
from barc4shadow.viz import plot_beamline
from orangecontrib.shadow4.util.shadow4_objects import ShadowData
from orangecontrib.esrf.util.matplotlib_tools import SnapshotNavigationToolbar


class OWBeamlineLayout(OWWidget):
    name = "Beamline Layout"
    description = "Plot a SHADOW4 beamline layout with barc4shadow"
    icon = "icons/uicons_progress-bar-dotted-line-half.png"
    priority = 5
    keywords = ["barc", "barc4shadow", "beamline", "layout", "shadow4"]

    want_main_area = 1

    class Inputs:
        shadow_data = Input("Shadow Data", ShadowData, default=True, auto_summary=False)

    show_source = Setting(True)
    show_experiment = Setting(True)
    show_empty_elements = Setting(False)
    draw_to_scale = Setting(False)

    def __init__(self):
        super().__init__()

        self._shadow_data = None
        self._canvas = None
        self._figure = None

        button_box = oasysgui.widgetBox(
            self.controlArea,
            "",
            addSpace=False,
            orientation="horizontal",
            width=390,
        )
        button = gui.button(button_box, self, "Plot Beamline", callback=self.plot_results)
        button.setStyleSheet(Styles.button_blue)

        settings_box = oasysgui.widgetBox(
            self.controlArea,
            "Layout",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        gui.checkBox(settings_box, self, "show_source", "Show source")
        gui.checkBox(settings_box, self, "show_experiment", "Show experiment")
        gui.checkBox(settings_box, self, "show_empty_elements", "Show empty elements")
        gui.checkBox(settings_box, self, "draw_to_scale", "Draw to scale")

        self.plot_tabs = oasysgui.tabWidget(self.mainArea)
        plot_tab = oasysgui.createTabPage(self.plot_tabs, "Beamline Layout")
        distances_tab = oasysgui.createTabPage(self.plot_tabs, "Distances Summary")

        self.plot_container = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_container)
        plot_tab.layout().addWidget(self.plot_container)

        self.distances_summary = oasysgui.textArea(height=560, noWrap=True)
        self.distances_summary.setFont(
            QFontDatabase.systemFont(QFontDatabase.FixedFont)
        )
        distances_box = gui.widgetBox(
            distances_tab,
            "",
            addSpace=True,
            orientation="horizontal",
        )
        distances_box.layout().addWidget(self.distances_summary)

        gui.rubber(self.controlArea)

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

            if self._shadow_data.beamline is None:
                raise ValueError("Shadow Data does not contain an S4 beamline.")

            layout = s4_beamline_to_layout(self._shadow_data.beamline)
            distances_text = layout_information(
                self._shadow_data.beamline,
                verbose=False,
            )

            self._clear_plots()
            fig, _ = plot_beamline(
                layout,
                show_source=bool(self.show_source),
                show_experiment=bool(self.show_experiment),
                show_empty_elements=bool(self.show_empty_elements),
                draw_to_scale=bool(self.draw_to_scale),
                plot=False,
            )
            self._set_figure(fig)
            self.distances_summary.setText(distances_text)

            self.setStatusMessage("Beamline layout updated.")
        except Exception as exception:
            self.distances_summary.setText(str(exception))
            self.setStatusMessage(str(exception))
            MessageDialog.message(
                parent=self,
                title="Beamline Layout Error",
                type="critical",
                message=str(exception),
            )

    def _set_figure(self, figure):
        canvas = FigureCanvas(figure)
        toolbar = SnapshotNavigationToolbar(canvas, self.plot_container)
        self.plot_layout.addWidget(toolbar)
        self.plot_layout.addWidget(canvas)
        self._canvas = canvas
        self._figure = figure
        canvas.draw()

    def _clear_plots(self):
        if self._figure is not None:
            plt.close(self._figure)

        self._canvas = None
        self._figure = None

        while self.plot_layout.count() > 0:
            item = self.plot_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


add_widget_parameters_to_module(__name__)
