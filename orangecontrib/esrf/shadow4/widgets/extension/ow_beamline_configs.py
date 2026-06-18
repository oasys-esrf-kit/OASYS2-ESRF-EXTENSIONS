from AnyQt.QtWidgets import QLineEdit, QWidget, QVBoxLayout
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import MultiInput

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import MessageDialog, Styles
from oasys2.widget.widget import OWWidget

from barc4shadow.beamline import s4_beamline_to_layout
from barc4shadow.viz import plot_beamline_configs
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


class OWBeamlineConfigs(OWWidget):
    name = "Beamline Configs"
    description = "Compare multiple SHADOW4 beamline layouts with barc4shadow"
    icon = "icons/deep-learning.png"
    priority = 5
    keywords = ["barc", "barc4shadow", "beamline", "layout", "configs", "shadow4"]

    want_main_area = 1

    class Inputs:
        shadow_data = MultiInput("Shadow Data", ShadowData, default=True, auto_summary=False)

    show_source = Setting(True)
    show_experiment = Setting(True)
    show_empty_elements = Setting(False)
    draw_to_scale = Setting(False)
    config_labels = Setting([])

    def __init__(self):
        super().__init__()

        self._shadow_data = []
        self._label_editors = []
        self._canvases = []
        self._figures = []

        button_box = oasysgui.widgetBox(
            self.controlArea,
            "",
            addSpace=False,
            orientation="horizontal",
            width=390,
        )
        button = gui.button(button_box, self, "Plot Configs", callback=self.plot_results)
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

        self.labels_box = oasysgui.widgetBox(
            self.controlArea,
            "Config Labels",
            addSpace=True,
            orientation="vertical",
            width=390,
        )

        self.plot_tabs = oasysgui.tabWidget(self.mainArea)

        gui.rubber(self.controlArea)
        self._refresh_label_editors()

    @Inputs.shadow_data
    def set_shadow_data(self, index, shadow_data):
        self._ensure_input_slot(index)
        self._shadow_data[index] = shadow_data
        self._ensure_label_slot(index)
        self._refresh_label_editors()

        if shadow_data is not None:
            self.plot_results()

    @Inputs.shadow_data.insert
    def insert_shadow_data(self, index, shadow_data):
        self._shadow_data.insert(index, shadow_data)
        self.config_labels.insert(index, self._default_label(index))
        self._renumber_empty_labels()
        self._refresh_label_editors()

        if shadow_data is not None:
            self.plot_results()

    @Inputs.shadow_data.remove
    def remove_shadow_data(self, index):
        if index < len(self._shadow_data):
            self._shadow_data.pop(index)

        if index < len(self.config_labels):
            self.config_labels.pop(index)

        self._renumber_empty_labels()
        self._refresh_label_editors()

        if self._has_configs():
            self.plot_results()
        else:
            self._clear_plots()
            self.setStatusMessage("No Shadow Data inputs.")

    def plot_results(self):
        self.setStatusMessage("")

        try:
            configs = []
            labels = []

            for index, shadow_data in enumerate(self._shadow_data):
                if shadow_data is None:
                    continue

                if shadow_data.beamline is None:
                    raise ValueError(f"Config {index + 1} does not contain an S4 beamline.")

                configs.append(s4_beamline_to_layout(shadow_data.beamline))
                labels.append(self._label_at(index))

            if not configs:
                raise ValueError("No Shadow Data inputs received.")

            self._clear_plots()
            fig, _ = plot_beamline_configs(
                configs,
                labels,
                show_source=bool(self.show_source),
                show_experiment=bool(self.show_experiment),
                show_empty_elements=bool(self.show_empty_elements),
                draw_to_scale=bool(self.draw_to_scale),
                plot=False,
            )
            self._add_figure_tab("Beamline Configs", fig)

            self.setStatusMessage("Beamline configs updated.")
        except Exception as exception:
            self.setStatusMessage(str(exception))
            MessageDialog.message(
                parent=self,
                title="Beamline Configs Error",
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

    def _refresh_label_editors(self):
        while self.labels_box.layout().count() > 0:
            item = self.labels_box.layout().takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._label_editors = []

        for index in range(len(self._shadow_data)):
            self._ensure_label_slot(index)
            row = oasysgui.widgetBox(
                self.labels_box,
                "",
                addSpace=False,
                orientation="horizontal",
            )
            gui.label(row, self, f"Config {index + 1}")
            editor = QLineEdit(row)
            editor.setText(self.config_labels[index])
            editor.textChanged.connect(self._label_changed(index))
            row.layout().addWidget(editor)
            self._label_editors.append(editor)

    def _label_changed(self, index):
        def callback(text):
            self._ensure_label_slot(index)
            self.config_labels[index] = text

        return callback

    def _ensure_input_slot(self, index):
        while len(self._shadow_data) <= index:
            self._shadow_data.append(None)

    def _ensure_label_slot(self, index):
        while len(self.config_labels) <= index:
            self.config_labels.append(self._default_label(len(self.config_labels)))

        if not str(self.config_labels[index]).strip():
            self.config_labels[index] = self._default_label(index)

    def _label_at(self, index):
        self._ensure_label_slot(index)
        label = str(self.config_labels[index]).strip()
        return label if label else self._default_label(index)

    def _has_configs(self):
        return any(shadow_data is not None for shadow_data in self._shadow_data)

    @staticmethod
    def _default_label(index):
        return f"config {index + 1}"

    def _renumber_empty_labels(self):
        for index, label in enumerate(self.config_labels):
            if not str(label).strip():
                self.config_labels[index] = self._default_label(index)


add_widget_parameters_to_module(__name__)
