import sys
import numpy
from AnyQt.QtWidgets import QMessageBox
from cryptography.x509 import load_pem_x509_certificate
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input

from oasys2.widget import gui as oasysgui
from oasys2.widget.util.exchange import DataExchangeObject
from oasys2.widget.util import congruence
from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

from orangecontrib.xoppy.widgets.gui.ow_xoppy_widget import XoppyWidget

from syned.widget.widget_decorator import WidgetDecorator
import syned.beamline.beamline as synedb
import syned.storage_ring.magnetic_structures.insertion_device as synedid


try:
    from spectrum_builder import get_spectrum
    from spectrum_builder import list_detectors, list_isotopes
    SPECTRUM_BUILDER_INSTALLED = 1
except:
    SPECTRUM_BUILDER_INSTALLED = 0
    print("spectrum_builder not installed.")

class OWisotopeSpectrum(XoppyWidget, WidgetDecorator):
    name = "Isotope spectrum"
    id = "orange.widgets.isotope_spectrum"
    description = "Spectrum of isotope emission"
    icon = "icons/isotope.png"
    priority = 0.5
    category = ""
    keywords = ["xoppy", "isotop_spectrum"]

    detector_index              = Setting(0)
    isotop_index                = Setting(6)
    number_of_bins              = Setting(1024)
    number_of_signal_events     = Setting(100000)
    number_of_background_events = Setting(100000)
    normalization_type          = Setting(0)
    random_seed                 = Setting(42)
    energy_min                  = Setting(0.0)
    energy_max                  = Setting(200.0)

    # retrieve lists for the 3 detectors
    try:
        ldetectors = list_detectors()
        l0 = list_isotopes(ldetectors[0])
        l1 = list_isotopes(ldetectors[1])
        l2 = list_isotopes(ldetectors[2])
        # full list
        lall = sorted(set(l0 + l1 + l2))

    except:
        l0 = []
        l1 = []
        l2 = []
        lall = []
        ldetectors = []


    USEEMITTANCES=0

    def __init__(self):
        super().__init__(show_script_tab=True)

    def build_gui(self):

        box = oasysgui.widgetBox(self.controlArea, self.name + " Input Parameters", orientation="vertical", width=self.CONTROL_AREA_WIDTH-5)
        
        idx = -1 
        #
        #
        #
        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "detector_index", label=self.unitLabels()[idx],
                     items=self.ldetectors, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #
        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "isotop_index", label=self.unitLabels()[idx],
                     items=self.lall, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "number_of_bins",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "number_of_signal_events",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "number_of_background_events",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #
        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "normalization_type", label=self.unitLabels()[idx],
                     items=['Raw counts', 'Counts per second (cps)', 'Unit area'], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)
        #
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "random_seed",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "energy_min",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "energy_max",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

    def unitLabels(self):
         return ["Detector", "Isotope", "Number of bins", "Number of signal events", \
                 "Number of background events", "Normalization type", "Random seed", \
                 "Energy min [keV]", "Energy max [keV]"]

    def unitFlags(self):
         return ["True", "True", "True", "True", "True", "True", "True", "True", "True"]

    def get_help_name(self):
        return 'isotope_spectrum'

    def check_fields(self):
        self.number_of_bins = congruence.checkStrictlyPositiveNumber(self.number_of_bins, "number_of_bins")
        self.number_of_signal_events = congruence.checkPositiveNumber(self.number_of_signal_events, "number_of_signal_events")
        self.number_of_background_events = congruence.checkPositiveNumber(self.number_of_background_events, "number_of_background_events")
        self.random_seed = congruence.checkNumber(self.random_seed, "random_seed")
        self.energy_min = congruence.checkPositiveNumber(self.energy_min, "energy_min")
        self.energy_max = congruence.checkStrictlyPositiveNumber(self.energy_max, "energy_max")

    def plot_results(self, calculated_data, progressBarValue=80):
        if not self.view_type == 0:
            if not calculated_data is None:

                self.initializeTabs() # added by srio to avoid overlapping graphs

                self.view_type_combo.setEnabled(False)

                data = calculated_data.get_content("xoppy_data")
                # code = calculated_data.get_content("xoppy_code")

                try:
                    # Spectrum
                    title = "Isotope: %s, Detector: %s " % (self.lall[self.isotop_index], self.ldetectors[self.detector_index])
                    self.plot_data1D(data[:, 0] * 1e-3, data[:, 1], 0, 0, title=title,
                                     xtitle="Photon Energy [keV]", ytitle="Intensity [counts]",
                                     control=False, xlog=False, ylog=False)
                except Exception as e:
                    self.view_type_combo.setEnabled(True)
                    raise Exception("Data not plottable: bad content\n" + str(e))

                self.view_type_combo.setEnabled(True)
            else:
                raise Exception("Empty Data")

    def do_xoppy_calculation(self):

        if not SPECTRUM_BUILDER_INSTALLED:
            QMessageBox.information(self, "Missing installation",
                                    "Please: \n %s -m pip install spectrum-builder>=1.0.5" % sys.executable,
                                    QMessageBox.StandardButton.Ok)
            return

        detector = self.ldetectors[self.detector_index]
        isotope = self.lall[self.isotop_index]

        print("** list of available isotopes for the three different detectors **")
        print("           in  %s    %s     %s" % (self.ldetectors[0], self.ldetectors[1], self.ldetectors[2]))
        for i, isot in enumerate(self.lall):
            print(isot, isot in self.l0, isot in self.l1, isot in self.l2)

        if self.detector_index == 0:
            lnow = self.l0
        elif self.detector_index == 1:
            lnow = self.l1
        elif self.detector_index == 2:
            lnow = self.l2
        else:
            raise ValueError

        if isotope in lnow:
            parameters = {
                "detector"                    : detector,
                "isotope"                     : isotope,
                "number_of_bins"              : self.number_of_bins,
                "number_of_signal_events"     : self.number_of_signal_events,
                "number_of_background_events" : self.number_of_background_events,
                "normalization_type"          : self.normalization_type,
                "random_seed"                 : self.random_seed,
                "energy_min"                  : self.energy_min,
                "energy_max"                  : self.energy_max,
            }
            print(parameters)

            script = self.script_template().format_map(parameters)
            self.xoppy_script.set_code(script)

            print(isotope, self.isotop_index, detector, self.detector_index, isotope in self.lall)

            spectrum = get_spectrum(
                detector=detector,
                isotope=isotope,
                number_of_bins=self.number_of_bins,
                number_of_signal_events=self.number_of_signal_events,
                number_of_background_events=self.number_of_background_events,
                normalization_type=self.normalization_type,
                random_seed=self.random_seed,
                energy_range=(self.energy_min, self.energy_max),
            )
        else:
            spectrum = numpy.zeros((100,2))
            script = "# Error: Spectrum not found"
            self.xoppy_script.set_code(script)
            # raise ValueError("Isotope %s not supported for %s detector." % (isotope, detector))
            QMessageBox.information(self, "Missing spectrum",
                                    "Isotope %s not supported for %s detector." % (isotope, detector),
                                    QMessageBox.StandardButton.Ok)

        spectrum1 = spectrum.copy()
        spectrum1[:, 0] = spectrum[:, 0] * 1e3 # in eV
        return spectrum1, script

    def script_template(self):
        return """
#
# script to make the calculations (created by XOPPY:isotope_spectrum)
#
from spectrum_builder import get_spectrum

spectrum = get_spectrum(
    detector="{detector}",
    isotope="{isotope}",
    number_of_bins={number_of_bins},
    number_of_signal_events={number_of_signal_events},
    number_of_background_events={number_of_background_events},
    normalization_type={normalization_type},
    random_seed={random_seed},
    energy_range=({energy_min},{energy_max}),
    )

# plot
if True:
    from srxraylib.plot.gol import plot
    plot(spectrum[:, 0], spectrum[:, 1], xtitle="Photon energy [keV]",
         ytitle="Spectrum [counts]", grid=1,
         title="Isotope: {isotope}, Detector: {detector} ")

#
# end script
#
"""


    def extract_data_from_xoppy_output(self, calculation_output):
        spectrum, script = calculation_output

        calculated_data = DataExchangeObject("XOPPY", self.get_data_exchange_widget_name())

        calculated_data.add_content("xoppy_data", spectrum)
        calculated_data.add_content("xoppy_script", script)

        return calculated_data

    def get_data_exchange_widget_name(self):
        return "isotope_spectrum"

    def getTitles(self):
        return ['Spectrum']

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    import sys
    from AnyQt.QtWidgets import QMessageBox, QApplication
    app = QApplication(sys.argv)
    ow = OWisotopeSpectrum()
    ow.show()
    app.exec()
    ow.saveSettings()