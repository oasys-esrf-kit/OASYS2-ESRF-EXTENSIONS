from AnyQt.QtWidgets import QWidget, QVBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import MessageDialog, Styles
from oasys2.widget.widget import OWWidget

from barc4shadow.beamline import s4_beamline_to_layout
from barc4shadow.viz import plot_beamline
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


class OWBeamlineLayout(OWWidget):
    name = "Beamline Layout"
    description = "Plot a SHADOW4 beamline layout with barc4shadow"
    icon = "icons/uicons_progress-bar-dotted-line-half.png"
    priority = 4
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
        self._canvases = []
        self._figures = []

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

            self._clear_plots()
            fig, _ = plot_beamline(
                layout,
                show_source=bool(self.show_source),
                show_experiment=bool(self.show_experiment),
                show_empty_elements=bool(self.show_empty_elements),
                draw_to_scale=bool(self.draw_to_scale),
                plot=False,
            )
            self._add_figure_tab("Beamline Layout", fig)

            self.setStatusMessage("Beamline layout updated.")
        except Exception as exception:
            self.setStatusMessage(str(exception))
            MessageDialog.message(
                parent=self,
                title="Beamline Layout Error",
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


add_widget_parameters_to_module(__name__)
