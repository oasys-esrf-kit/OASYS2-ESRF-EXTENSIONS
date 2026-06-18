import contextlib
import copy
import io

from orangewidget import gui
from orangewidget.widget import Input, Output

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import Styles
from oasys2.widget.widget import OWWidget

from barc4beams import Beam
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


class OWBeamInfo(OWWidget):
    name = "Beam Info"
    description = "Convert Shadow4 data to a barc4beams Beam and print statistics"
    icon = "icons/info.png"
    priority = 1
    keywords = ["barc", "barc4beams", "beam", "statistics", "shadow4"]

    want_main_area = 1

    class Inputs:
        shadow_data = Input("Shadow Data", ShadowData, default=True, auto_summary=False)

    class Outputs:
        beam = Output("BARC Beam", Beam, default=True, auto_summary=False)

    def __init__(self):
        super().__init__()

        self._shadow_data = None
        self._barc_beam = None

        button_box = oasysgui.widgetBox(
            self.controlArea,
            "",
            addSpace=False,
            orientation="horizontal",
            width=390,
        )
        button = gui.button(button_box, self, "Compute Beam Info", callback=self.compute_beam_info)
        button.setStyleSheet(Styles.button_blue)

        info_box = oasysgui.widgetBox(
            self.controlArea,
            "Input",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        gui.label(info_box, self, "Accepts Shadow Data and outputs a barc4beams Beam.")

        self.stats_output = oasysgui.textArea(height=560, width=760)
        output_box = gui.widgetBox(
            self.mainArea,
            "Beam statistics",
            addSpace=True,
            orientation="horizontal",
        )
        output_box.layout().addWidget(self.stats_output)

        gui.rubber(self.controlArea)

    @Inputs.shadow_data
    def set_shadow_data(self, shadow_data):
        self._shadow_data = shadow_data

        if shadow_data is not None:
            self.compute_beam_info()

    def compute_beam_info(self):
        self.setStatusMessage("")

        try:
            if self._shadow_data is None:
                raise ValueError("No Shadow Data input received.")

            if self._shadow_data.beam is None:
                raise ValueError("Shadow Data does not contain a beam.")

            shadow_beam = self._copy_shadow_beam(self._shadow_data.beam)
            self._barc_beam = Beam(shadow_beam, code="s4")

            stats_text, stats = self._format_stats(self._barc_beam)
            self.stats_output.setText(stats_text)
            print(stats_text)

            self.Outputs.beam.send(self._barc_beam)
            self.setStatusMessage("BARC Beam emitted.")
        except Exception as exception:
            self._barc_beam = None
            self.Outputs.beam.send(None)
            self.stats_output.setText(str(exception))
            self.setStatusMessage(str(exception))

    @staticmethod
    def _copy_shadow_beam(shadow_beam):
        if hasattr(shadow_beam, "duplicate"):
            return shadow_beam.duplicate()

        return copy.deepcopy(shadow_beam)

    @staticmethod
    def _format_stats(barc_beam):
        stream = io.StringIO()

        with contextlib.redirect_stdout(stream):
            stats = barc_beam.stats(verbose=True)

        text = stream.getvalue().strip()
        if not text:
            text = repr(stats)

        return text, stats


add_widget_parameters_to_module(__name__)
