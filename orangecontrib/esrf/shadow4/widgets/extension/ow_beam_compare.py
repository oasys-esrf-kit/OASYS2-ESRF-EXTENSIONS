import copy

from orangewidget import gui
from orangewidget.widget import Input

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import Styles
from oasys2.widget.widget import OWWidget

from barc4beams import Beam, compare_beams
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


class OWBeamCompare(OWWidget):
    name = "Beam Compare"
    description = "Compare two Shadow4 beams with barc4beams"
    icon = "icons/scales.png"
    priority = 2
    keywords = ["barc", "barc4beams", "beam", "compare", "shadow4"]

    want_main_area = 1

    class Inputs:
        shadow_data_1 = Input("Shadow Data 1", ShadowData, default=True, auto_summary=False)
        shadow_data_2 = Input("Shadow Data 2", ShadowData, auto_summary=False)

    def __init__(self):
        super().__init__()

        self._shadow_data_1 = None
        self._shadow_data_2 = None
        self._comparison = None

        button_box = oasysgui.widgetBox(
            self.controlArea,
            "",
            addSpace=False,
            orientation="horizontal",
            width=390,
        )
        button = gui.button(button_box, self, "Compare Beams", callback=self.compare)
        button.setStyleSheet(Styles.button_blue)

        info_box = oasysgui.widgetBox(
            self.controlArea,
            "Input",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        gui.label(info_box, self, "Accepts two Shadow Data inputs and compares their beams.")

        self.compare_output = oasysgui.textArea(height=560, width=760)
        output_box = gui.widgetBox(
            self.mainArea,
            "Beam comparison",
            addSpace=True,
            orientation="horizontal",
        )
        output_box.layout().addWidget(self.compare_output)

        gui.rubber(self.controlArea)

    @Inputs.shadow_data_1
    def set_shadow_data_1(self, shadow_data):
        self._shadow_data_1 = shadow_data

        if self._shadow_data_1 is not None and self._shadow_data_2 is not None:
            self.compare()

    @Inputs.shadow_data_2
    def set_shadow_data_2(self, shadow_data):
        self._shadow_data_2 = shadow_data

        if self._shadow_data_1 is not None and self._shadow_data_2 is not None:
            self.compare()

    def compare(self):
        self.setStatusMessage("")

        try:
            beam_1 = self._to_barc_beam(self._shadow_data_1, "Shadow Data 1")
            beam_2 = self._to_barc_beam(self._shadow_data_2, "Shadow Data 2")

            self._comparison = compare_beams(beam_1, beam_2)

            comparison_text = str(self._comparison)
            self.compare_output.setText(comparison_text)
            print(self._comparison)

            if self._comparison.same:
                self.setStatusMessage("Beams are the same.")
            else:
                self.setStatusMessage("Beams differ.")
        except Exception as exception:
            self._comparison = None
            self.compare_output.setText(str(exception))
            self.setStatusMessage(str(exception))

    @classmethod
    def _to_barc_beam(cls, shadow_data, input_name):
        if shadow_data is None:
            raise ValueError(f"No {input_name} input received.")

        if shadow_data.beam is None:
            raise ValueError(f"{input_name} does not contain a beam.")

        return Beam(cls._copy_shadow_beam(shadow_data.beam), code="s4")

    @staticmethod
    def _copy_shadow_beam(shadow_beam):
        if hasattr(shadow_beam, "duplicate"):
            return shadow_beam.duplicate()

        return copy.deepcopy(shadow_beam)


add_widget_parameters_to_module(__name__)
