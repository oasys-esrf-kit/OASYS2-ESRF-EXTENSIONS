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
from oasys2.widget.gui import ConfirmDialog, MessageDialog, Styles
from oasys2.widget.widget import OWWidget

from barc4beams import Beam
from barc4beams.viz import (
    plot_beam,
    plot_divergence,
    plot_energy,
    plot_energy_vs_intensity,
    plot_intensity,
    plot_phase_space,
)
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


COLOR_MAPS = ["viridis", "plasma", "turbo", "magma", "terrain"]


class OWBeamPlot(OWWidget):
    name = "Beam Plot"
    description = "Plot a barc4beams Beam"
    icon = "icons/chart-scatter.png"
    priority = 2
    keywords = ["barc", "barc4beams", "beam", "plot", "divergence", "phase space"]

    want_main_area = 1

    class Inputs:
        shadow_data = Input("Shadow Data", ShadowData, default=True, auto_summary=False)

    class Outputs:
        beam = Output("BARC Beam", Beam, default=True, auto_summary=False)

    plot_type = Setting(0)
    phase_direction = Setting(2)
    mode = Setting(0)
    aspect_ratio = Setting(True)
    color = Setting(1)
    use_x_range = Setting(False)
    x_range_min = Setting(0.0)
    x_range_max = Setting(0.0)
    use_y_range = Setting(False)
    y_range_min = Setting(0.0)
    y_range_max = Setting(0.0)
    bins = Setting(0)
    z_offset = Setting(0.0)

    SCATTER_CONFIRM_RAYS = 20000
    SCATTER_FORCE_HIST_RAYS = 50000

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
        button = gui.button(button_box, self, "Plot Beam", callback=self.plot_results)
        button.setStyleSheet(Styles.button_blue)

        settings_box = oasysgui.widgetBox(
            self.controlArea,
            "Plot",
            addSpace=True,
            orientation="vertical",
            width=390,
        )

        gui.comboBox(
            settings_box,
            self,
            "plot_type",
            label="Plot",
            labelWidth=160,
            items=[
                "Beam",
                "Divergence",
                "Phase Space",
                "Energy",
                "Intensity",
                "Energy vs Intensity",
            ],
            sendSelectedValue=False,
            orientation="horizontal",
            callback=self._update_visibility,
        )

        self.phase_direction_box = oasysgui.widgetBox(
            settings_box,
            "",
            addSpace=False,
            orientation="vertical",
        )
        gui.comboBox(
            self.phase_direction_box,
            self,
            "phase_direction",
            label="Direction",
            labelWidth=160,
            items=["X", "Y", "Both"],
            sendSelectedValue=False,
            orientation="horizontal",
        )

        self.mode_box = oasysgui.widgetBox(
            settings_box,
            "",
            addSpace=False,
            orientation="vertical",
        )
        gui.comboBox(
            self.mode_box,
            self,
            "mode",
            label="Mode",
            labelWidth=160,
            items=["scatter", "hist2d"],
            sendSelectedValue=False,
            orientation="horizontal",
        )

        self.aspect_ratio_box = oasysgui.widgetBox(
            settings_box,
            "",
            addSpace=False,
            orientation="vertical",
        )
        gui.checkBox(self.aspect_ratio_box, self, "aspect_ratio", "Aspect ratio")

        self.color_box = oasysgui.widgetBox(
            settings_box,
            "",
            addSpace=False,
            orientation="vertical",
        )
        gui.comboBox(
            self.color_box,
            self,
            "color",
            label="Color",
            labelWidth=160,
            orientation="horizontal",
            items=COLOR_MAPS,
            sendSelectedValue=False,
        )
        oasysgui.lineEdit(
            settings_box,
            self,
            "bins",
            "Number of Bins (0 = auto)",
            labelWidth=160,
            valueType=int,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            settings_box,
            self,
            "z_offset",
            "Z offset [m]",
            labelWidth=160,
            valueType=float,
            orientation="horizontal",
        )

        self.range_box = oasysgui.widgetBox(
            self.controlArea,
            "Ranges",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        gui.checkBox(self.range_box, self, "use_x_range", "Set X range", callback=self._update_visibility)
        self.x_range_box = oasysgui.widgetBox(self.range_box, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(
            self.x_range_box,
            self,
            "x_range_min",
            "X min",
            labelWidth=160,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.x_range_box,
            self,
            "x_range_max",
            "X max",
            labelWidth=160,
            valueType=float,
            orientation="horizontal",
        )

        gui.checkBox(self.range_box, self, "use_y_range", "Set Y range", callback=self._update_visibility)
        self.y_range_box = oasysgui.widgetBox(self.range_box, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(
            self.y_range_box,
            self,
            "y_range_min",
            "Y min",
            labelWidth=160,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.y_range_box,
            self,
            "y_range_max",
            "Y max",
            labelWidth=160,
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

            mode = self._resolve_plot_mode(self._beam) if self._uses_mode() else self._plot_mode()

            self._clear_plots()

            common_kwargs = {
                "mode": mode,
                "aspect_ratio": bool(self.aspect_ratio),
                "color": self._color_index(),
                "x_range": self._range_or_none(self.use_x_range, self.x_range_min, self.x_range_max),
                "y_range": self._range_or_none(self.use_y_range, self.y_range_min, self.y_range_max),
                "bins": self._bins_or_none(),
                "z_offset": float(self.z_offset),
                "plot": False,
            }

            df = self._beam.df

            if self.plot_type == 0:
                fig, _ = plot_beam(df, **common_kwargs)
                self._add_figure_tab("Beam", fig)
            elif self.plot_type == 1:
                fig, _ = plot_divergence(df, **common_kwargs)
                self._add_figure_tab("Divergence", fig)
            elif self.plot_type == 2:
                direction = self._phase_direction()
                result = plot_phase_space(df, direction=direction, **common_kwargs)
                if direction == "both":
                    (fig_x, _), (fig_y, _) = result
                    self._add_figure_tab("Phase Space X", fig_x)
                    self._add_figure_tab("Phase Space Y", fig_y)
                else:
                    fig, _ = result
                    self._add_figure_tab(f"Phase Space {direction.upper()}", fig)
            elif self.plot_type == 3:
                fig, _ = plot_energy(df, bins=self._bins_or_none(), plot=False)
                self._add_figure_tab("Energy", fig)
            elif self.plot_type == 4:
                fig, _ = plot_intensity(df, bins=self._bins_or_none(), plot=False)
                self._add_figure_tab("Intensity", fig)
            else:
                energy_intensity_kwargs = dict(common_kwargs)
                energy_intensity_kwargs.pop("z_offset")
                fig, _ = plot_energy_vs_intensity(df, **energy_intensity_kwargs)
                self._add_figure_tab("Energy vs Intensity", fig)

            self.Outputs.beam.send(self._beam)
            self.setStatusMessage("Plot updated.")
        except Exception as exception:
            self._beam = None
            self.Outputs.beam.send(None)
            self.setStatusMessage(str(exception))
            MessageDialog.message(
                parent=self,
                title="Plot Error",
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
        is_phase_space = self.plot_type == 2
        is_1d = self.plot_type in (3, 4)
        is_2d = not is_1d

        self.phase_direction_box.setVisible(is_phase_space)
        self.mode_box.setVisible(is_2d)
        self.aspect_ratio_box.setVisible(is_2d)
        self.color_box.setVisible(is_2d)
        self.range_box.setVisible(is_2d)
        self.x_range_box.setVisible(is_2d and bool(self.use_x_range))
        self.y_range_box.setVisible(is_2d and bool(self.use_y_range))

    def _plot_mode(self):
        return "scatter" if self.mode == 0 else "hist2d"

    def _uses_mode(self):
        return self.plot_type in (0, 1, 2, 5)

    def _resolve_plot_mode(self, beam):
        mode = self._plot_mode()

        if mode != "scatter":
            return mode

        good_rays = self._good_rays_count(beam)

        if good_rays > self.SCATTER_FORCE_HIST_RAYS:
            MessageDialog.message(
                parent=self,
                title="Large Scatter Plot",
                type="warning",
                message=(
                    f"Scatter plotting {good_rays:,} good rays is too heavy for the GUI. "
                    "Switching to hist2d."
                ),
            )
            self.mode = 1
            return "hist2d"

        if good_rays > self.SCATTER_CONFIRM_RAYS:
            proceed = ConfirmDialog.confirmed(
                parent=self,
                title="Large Scatter Plot",
                message=(
                    f"Scatter plotting {good_rays:,} good rays may be slow or make "
                    "the GUI temporarily unresponsive.\n\nProceed with scatter?"
                ),
            )

            if not proceed:
                self.mode = 1
                return "hist2d"

        return "scatter"

    def _phase_direction(self):
        return ["x", "y", "both"][self.phase_direction]

    def _bins_or_none(self):
        bins = int(self.bins)
        return None if bins <= 0 else bins

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

        shadow_beam = OWBeamPlot._copy_shadow_beam(shadow_data.beam)
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

    @staticmethod
    def _good_rays_count(beam):
        df = beam.df

        if "lost_ray_flag" not in df.columns:
            return len(df)

        return int((df["lost_ray_flag"] == 0).sum())


add_widget_parameters_to_module(__name__)
