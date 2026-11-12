import os
import sys
import tempfile
import numpy
import scipy.constants as codata
from AnyQt.QtWidgets import QMessageBox
from orangewidget import gui
from orangewidget.settings import Setting

from oasys2.widget import gui as oasysgui
from oasys2.widget.util.exchange import DataExchangeObject
from oasys2.widget.util import congruence
from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

from orangecontrib.xoppy.widgets.gui.ow_xoppy_widget import XoppyWidget

from syned.widget.widget_decorator import WidgetDecorator

try:
    from radionuclide_emission_db import EmissionLine, MATERIALS, material_filter
    RADIONUCLIDE_EMISSION_DB_INSTALLED = 1
except:
    RADIONUCLIDE_EMISSION_DB_INSTALLED = 0
    print("radionuclide_emission_db not installed.")


MAX_ISOTOPES = 3
MAX_FILTERS = 3
FILTER_MIN_ENERGY = 1.0 # keV, lowest energy of the NIST tables: lines below are removed by the filters

RADIATION_TYPES = [
    ("Gamma", "X-ray", "Annihilation photon"),
    ("Gamma", "Annihilation photon"),
    ("X-ray",),
]

INSTALL_MESSAGE = "Please install radionuclide-emission-db:\n\n %s -m pip install radionuclide-emission-db" % sys.executable

#
# On-demand access to MIRDspecs (ICRP-107) photon emission spectra via radionuclide-emission-db.
#
# Nothing is downloaded at installation:
# - the list of isotopes is always read on-the-fly from the MIRDspecs index (network required);
# - the CSV of an isotope is downloaded only when first used.
#
# Spectra are cached in a user-writable directory (same convention as DABAX):
# ~/.local/share/MIRDspecs (Linux, or $XDG_DATA_HOME/MIRDspecs), %LOCALAPPDATA%\MIRDspecs (Windows),
# ~/Library/Application Support/MIRDspecs (macOS).
#
def _proxies_info():
    """Proxies used by urllib (e.g. set by OASYS from Preferences/Network or the system settings)."""
    import urllib.request
    proxies = urllib.request.getproxies()
    return "proxies used: %s" % (proxies if proxies else "none")

def _csv_name(isotope):
    return "%s Summary Spectrum.csv" % isotope

def get_mirdspecs_directory():
    """Platform-specific user directory where MIRDspecs files are cached (created if absent)."""
    home = os.path.expanduser("~")

    if sys.platform.startswith("win"): base = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
    elif sys.platform == "darwin":     base = os.path.join(home, "Library", "Application Support")
    else:                              base = os.environ.get("XDG_DATA_HOME", os.path.join(home, ".local", "share"))

    directory = os.path.join(base, "MIRDspecs")
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError: # not writable: use a temporary directory
        directory = os.path.join(tempfile.gettempdir(), "MIRDspecs")
        os.makedirs(directory, exist_ok=True)
    return directory

def _isotope_sort_key(isotope):
    # element symbol, then mass number, then metastable flag (e.g. Ag-99 < Ag-100 < Ag-100m)
    element, mass = isotope.split("-")
    return element, int(mass.rstrip("m")), mass.endswith("m")

def _read_url(url, timeout):
    """
    Read a URL with a fresh urllib opener (honouring the proxy environment variables), so that the
    request does not depend on a global opener installed by other packages (e.g. dabax installs one
    with an unverified SSL context). HTTP errors report the server and the beginning of its answer.
    """
    import urllib.request
    from urllib.error import HTTPError
    request = urllib.request.Request(url, headers={"User-Agent": "radionuclide-emission-db/0.4.5 (research tool)"})
    try:
        with urllib.request.build_opener().open(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except HTTPError as e:
        try:    body = e.read()[:200].decode("utf-8", errors="replace").replace("\n", " ")
        except: body = ""
        raise Exception("HTTP Error %s: %s (server: %s)\n%s" % (e.code, e.reason, e.headers.get("server"), body))

def get_isotope_list(timeout=10, return_source=False):
    """
    List of the isotopes in MIRDspecs, sorted by element and mass number, always read on-the-fly
    from the online MIRDspecs index (network required; nothing is cached). Note that the index
    also lists isotopes without photon emission (e.g. C-14).

    With return_source=True, returns (isotopes, source), source being a text saying where the
    list comes from.
    """
    from radionuclide_emission_db.cache import INDEX_URL, _IndexParser  # parser of the index page

    try:
        parser = _IndexParser()
        parser.feed(_read_url(INDEX_URL, timeout))
        if not parser.names:
            raise Exception("No isotopes found in the MIRDspecs index; page format may have changed")
        isotopes = sorted(parser.names, key=_isotope_sort_key)
    except Exception as e:
        raise Exception("Cannot read the MIRDspecs index %s (network required):\n%s\n(%s)" % (
            INDEX_URL, str(e), _proxies_info()))

    source = "read from the MIRDspecs index %s" % INDEX_URL
    return (isotopes, source) if return_source else isotopes

def _load(isotope, cache_dir, radiation_types, verbose):
    from radionuclide_emission_db import Radionuclide
    nuclide = Radionuclide(isotope, cache_dir=cache_dir)
    csv_file = os.path.join(cache_dir, _csv_name(isotope))
    cached = os.path.isfile(csv_file)
    spectrum = nuclide.load(radiation_types=radiation_types)
    if verbose:
        if cached: print("%s: read from cached file %s" % (isotope, csv_file))
        else:      print("%s: downloaded from %s\n    saved in %s" % (isotope, nuclide.source_url, csv_file))
    return spectrum

def load_isotope(isotope, radiation_types=("Gamma", "X-ray", "Annihilation photon"), verbose=False):
    """
    Return the radionuclide_emission_db.Spectrum of an isotope, downloading its CSV into the
    cache directory if not already there. With verbose=True, print where the data comes from.
    """
    try:
        return _load(isotope, get_mirdspecs_directory(), radiation_types, verbose)
    except OSError: # downloaded but not writable: retry in a temporary directory
        return _load(isotope, os.path.join(tempfile.gettempdir(), "MIRDspecs"), radiation_types, verbose)
    except RuntimeError as e:
        raise Exception("Could not download the MIRDspecs spectrum of %s (network needed the first "
                        "time an isotope is used):\n%s\n%s\n(%s)" % (isotope, str(e), str(e.__cause__ or ""),
                                                                _proxies_info()))
    except ValueError:
        raise Exception("No photon lines of the selected radiation type(s) %s for %s" % (radiation_types, isotope))

def get_nist_directory():
    """Cache directory of the NIST attenuation tables (downloaded on demand, one file per element)."""
    return os.path.join(get_mirdspecs_directory(), "nist-attenuation")

def filter_density(material, density):
    """Density [g/cm3] of a filter. '?' means default: from radionuclide-emission-db MATERIALS
    (e.g. Pb, Al, Cu, W, water, NaI, CZT), otherwise the xraylib density of the element."""
    if str(density).strip() not in ("?", ""):
        return float(density)
    entry = MATERIALS.get(material.strip().lower())
    if entry: return entry[1]
    try:
        import xraylib
        return float(xraylib.ElementDensity(xraylib.SymbolToAtomicNumber(material.strip())))
    except Exception:
        raise Exception("Unknown density for filter material %s: please enter it" % material)

def get_filter(material, thickness_mm, density, verbose=False):
    """MaterialFilter (radionuclide-emission-db, NIST SRD 126 tables cached on demand)."""
    import xraylib
    directory = get_nist_directory()
    mf = material_filter(material, thickness_mm, density_g_cm3=filter_density(material, density),
                         attenuation_data_dir=directory)
    if verbose: # info on the NIST tables used (the download, if needed, is done by the library)
        formula = (MATERIALS.get(material.strip().lower()) or (material,))[0]
        for z in xraylib.CompoundParser(formula)["Elements"]:
            file = os.path.join(directory, "z%02d.json" % z)
            print("    Z=%d: %s %s" % (z, "read from cached file" if os.path.exists(file) else
                                       "downloaded from NIST and saved in", file))
    return mf

def filters_transmission(energy_keV, filters):
    """Transmission of the lines through all filters (lines below FILTER_MIN_ENERGY are removed: 0)."""
    t = numpy.ones(len(energy_keV))
    for i, e in enumerate(energy_keV):
        if e < FILTER_MIN_ENERGY:
            t[i] = 0.0
        else:
            for f in filters:
                t[i] *= numpy.exp(-float(f.mu_cm_inv(e)) * f.thickness_mm / 10)
    return t

def merge_lines(energy_eV, intensity):
    """Sum the intensities of lines with the same energy. Returns an array (nlines, 2): energy [eV], intensity."""
    energies, inverse = numpy.unique(numpy.asarray(energy_eV, dtype=float), return_inverse=True)
    summed = numpy.zeros(energies.size)
    numpy.add.at(summed, inverse, numpy.asarray(intensity, dtype=float))
    return numpy.column_stack((energies, summed))

def energy_grid(energy_min_eV, energy_max_eV, npoints=None, step_eV=None):
    """
    Regular energy grid [eV] starting at energy_min_eV, defined either by the number of points
    (last point = energy_max_eV) or by the step (exact step; the last point is the first one
    >= energy_max_eV, so that all lines up to energy_max_eV are inside the grid).
    """
    if step_eV is None:
        return numpy.linspace(energy_min_eV, energy_max_eV, int(npoints))
    n = int(numpy.ceil((energy_max_eV - energy_min_eV) / step_eV - 1e-9)) + 1
    return energy_min_eV + step_eV * numpy.arange(max(n, 2))

def lines_to_binned_spectrum(energy_eV, photons_per_s, energy):
    """
    Bin discrete emission lines on a regular energy grid, in the standard XOPPY source format
    (as e.g. XWIGGLER) used by POWER.

    Each line is shared between its two neighbouring grid points with linear weights (1-f, f),
    which preserves both its number of photons and its power (the weighted mean of the grid
    energies is the line energy). Densities are per eV (weights / step); the values at the two end
    points are doubled because the trapezoid rule (used by POWER) gives them half weight. Then the
    trapezoid integrals of the flux density and of the spectral power give exactly the totals
    of the lines.

    Returns an array (grid points, 4): energy [eV], flux [photons/s/0.1%bw], spectral power [W/eV],
    cumulated power [W].
    """
    energy = numpy.asarray(energy, dtype=float)  # regular grid [eV], e.g. from energy_grid()
    step = energy[1] - energy[0]
    e = numpy.asarray(energy_eV, dtype=float)
    n = numpy.asarray(photons_per_s, dtype=float)
    position = (e - energy[0]) / step
    k = numpy.clip(numpy.floor(position).astype(int), 0, energy.size - 2)
    f = position - k
    weights = numpy.zeros(energy.size)
    numpy.add.at(weights, k, n * (1 - f))
    numpy.add.at(weights, k + 1, n * f)
    density = weights / step  # photons/s/eV
    density[0] *= 2
    density[-1] *= 2
    spectral_power = density * energy * codata.e  # W/eV
    cumulated_power = numpy.concatenate(([0.0], numpy.cumsum(0.5 * (spectral_power[1:] + spectral_power[:-1]) * step)))
    return numpy.column_stack((energy, density * 1e-3 * energy, spectral_power, cumulated_power))

class OWisotopeSpectrum(XoppyWidget, WidgetDecorator):
    name = "Isotope spectrum"
    id = "orange.widgets.isotope_spectrum"
    description = "Photon emission lines of radionuclides (ICRP-107/MIRDspecs)"
    icon = "icons/isotope.png"
    priority = 20
    category = ""
    keywords = ["xoppy", "isotope_spectrum", "radionuclide", "gamma"]

    number_of_isotopes  = Setting(1)   # combo index: 0->1 isotope, 1->2, 2->3
    isotope_1           = Setting("Cs-137")
    isotope_2           = Setting("Ba-137m")
    isotope_3           = Setting("Co-60")
    activity_1          = Setting(1.0)
    activity_2          = Setting(0.944)
    activity_3          = Setting(1.0)
    radiation_type      = Setting(0)
    intensity_units     = Setting(0)   # 0=photons/s, 1=photons in acquisition time
    acquisition_time    = Setting(1.0)
    energy_min          = Setting(1.0)
    energy_max          = Setting(3000.0)
    binning             = Setting(0)   # 0=number of points, 1=bin size
    number_of_points    = Setting(10000)
    bin_size            = Setting(0.3)  # keV
    number_of_filters   = Setting(0)    # 0=no filters, 1, 2, 3
    filter_material_1   = Setting("Pb")
    filter_material_2   = Setting("Al")
    filter_material_3   = Setting("Cu")
    filter_thickness_1  = Setting(1.0)  # mm
    filter_thickness_2  = Setting(1.0)
    filter_thickness_3  = Setting(1.0)
    filter_density_1    = Setting("?")  # g/cm3, ?=default
    filter_density_2    = Setting("?")
    filter_density_3    = Setting("?")

    def __init__(self):
        # list of isotopes read on-the-fly from the MIRDspecs index (network required)
        self.isotope_list_error = None
        try:
            self.isotope_list, self.isotope_list_source = get_isotope_list(return_source=True)
        except Exception as e:
            print(str(e))
            self.isotope_list, self.isotope_list_source = [], ""
            self.isotope_list_error = str(e)
        # keep the selected isotopes in the combo boxes even if the list is not available
        for i in range(1, MAX_ISOTOPES + 1):
            if getattr(self, "isotope_%d" % i) not in self.isotope_list:
                self.isotope_list = self.isotope_list + [getattr(self, "isotope_%d" % i)]
        super().__init__(show_script_tab=True)
        self.update_script()  # script available before the calculation (e.g. for debugging)

    def build_gui(self):

        box0 = oasysgui.widgetBox(self.controlArea, self.name + " Input Parameters", orientation="vertical", width=self.CONTROL_AREA_WIDTH-5)

        box = oasysgui.widgetBox(self.controlArea, " Isotopes", orientation="vertical", width=self.CONTROL_AREA_WIDTH-5)


        idx = -1

        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "number_of_isotopes", label=self.unitLabels()[idx],
                     items=[str(i + 1) for i in range(MAX_ISOTOPES)], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        for i in range(1, MAX_ISOTOPES + 1):
            idx += 1
            box1 = gui.widgetBox(box)
            gui.comboBox(box1, self, "isotope_%d" % i, label=self.unitLabels()[idx],
                         items=self.isotope_list, sendSelectedValue=True, searchable=True,
                         orientation="horizontal", labelWidth=250)
            self.show_at(self.unitFlags()[idx], box1)

            idx += 1
            box1 = gui.widgetBox(box)
            oasysgui.lineEdit(box1, self, "activity_%d" % i, label=self.unitLabels()[idx],
                              valueType=float, orientation="horizontal", labelWidth=250)
            self.show_at(self.unitFlags()[idx], box1)

        box = oasysgui.widgetBox(self.controlArea, " Emission", orientation="vertical", width=self.CONTROL_AREA_WIDTH-5)

        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "radiation_type", label=self.unitLabels()[idx],
                     items=["All photons", "Gamma [from nucleus] + annihilation", "X-ray [from atomic shells]"], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "intensity_units", label=self.unitLabels()[idx],
                     items=["Photons/s", "Photons in acquisition time"], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "acquisition_time", label=self.unitLabels()[idx],
                          valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "energy_min", label=self.unitLabels()[idx],
                          valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "energy_max", label=self.unitLabels()[idx],
                          valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "binning", label=self.unitLabels()[idx],
                     items=["Number of points", "Bin size"], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "number_of_points", label=self.unitLabels()[idx],
                          valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "bin_size", label=self.unitLabels()[idx],
                          valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        box = oasysgui.widgetBox(self.controlArea, " Filtering", orientation="vertical", width=self.CONTROL_AREA_WIDTH-5)


        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "number_of_filters", label=self.unitLabels()[idx],
                     items=["None"] + [str(i + 1) for i in range(MAX_FILTERS)], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        for i in range(1, MAX_FILTERS + 1):
            for name, value_type in (("filter_material_%d", str), ("filter_thickness_%d", float), ("filter_density_%d", str)):
                idx += 1
                box1 = gui.widgetBox(box)
                oasysgui.lineEdit(box1, self, name % i, label=self.unitLabels()[idx],
                                  valueType=value_type, orientation="horizontal", labelWidth=250)
                self.show_at(self.unitFlags()[idx], box1)

    def unitLabels(self):
        labels = ["Number of isotopes"]
        for i in range(1, MAX_ISOTOPES + 1):
            labels += ["Isotope %d" % i, "   Activity %d [Bq]" % i]
        labels += ["Radiation type", "Intensity units", "Acquisition time [s]",
                   "Energy min [keV]", "Energy max [keV]", "Binning of the energy grid", "   Number of energy points", "   Bin size [keV]",
                   "Internal filters"]
        for i in range(1, MAX_FILTERS + 1):
            labels += ["Filter %d material (element or formula)" % i, "   Filter %d thickness [mm]" % i,
                       "   Filter %d density [g/cm3] (?=default)" % i]
        return labels

    def unitFlags(self):
        flags = ["True"]
        for i in range(1, MAX_ISOTOPES + 1):
            flags += ["self.number_of_isotopes >= %d" % (i - 1)] * 2
        flags += ["True", "True", "self.intensity_units == 1", "True", "True", "True",
                  "self.binning == 0", "self.binning == 1", "True"]
        for i in range(1, MAX_FILTERS + 1):
            flags += ["self.number_of_filters >= %d" % i] * 3
        return flags

    def get_help_name(self):
        return 'isotope_spectrum'

    def help1(self): # todo remove this overrided method after placing the doc file in wofryimpl
        from orangecontrib.xoppy.widgets.gui.text_window import TextWindow
        import orangecontrib.esrf.xoppy.data as data_package
        filename = os.path.join(os.path.dirname(data_package.__file__), self.get_help_name() + '.txt')
        TextWindow(file=filename, parent=self)

    def check_fields(self):
        for i in range(1, self.number_of_isotopes + 2):
            setattr(self, "activity_%d" % i,
                    congruence.checkPositiveNumber(getattr(self, "activity_%d" % i), "Activity %d" % i))
        self.acquisition_time = congruence.checkStrictlyPositiveNumber(self.acquisition_time, "Acquisition time")
        self.energy_min = congruence.checkStrictlyPositiveNumber(self.energy_min, "Energy min")
        self.energy_max = congruence.checkStrictlyPositiveNumber(self.energy_max, "Energy max")
        congruence.checkGreaterThan(self.energy_max, self.energy_min, "Energy max", "Energy min")
        if self.binning == 0:
            self.number_of_points = congruence.checkStrictlyPositiveNumber(self.number_of_points, "Number of energy points")
            congruence.checkGreaterOrEqualThan(self.number_of_points, 2, "Number of energy points", "2")
        else:
            self.bin_size = congruence.checkStrictlyPositiveNumber(self.bin_size, "Bin size")
        for i in range(1, self.number_of_filters + 1):
            congruence.checkEmptyString(getattr(self, "filter_material_%d" % i), "Filter %d material" % i)
            setattr(self, "filter_thickness_%d" % i,
                    congruence.checkPositiveNumber(getattr(self, "filter_thickness_%d" % i), "Filter %d thickness" % i))
            if str(getattr(self, "filter_density_%d" % i)).strip() not in ("?", ""):
                congruence.checkStrictlyPositiveNumber(float(getattr(self, "filter_density_%d" % i)), "Filter %d density" % i)

    def _energy_grid(self):
        if self.binning == 0:
            return energy_grid(self.energy_min * 1e3, self.energy_max * 1e3, npoints=self.number_of_points)
        else:
            return energy_grid(self.energy_min * 1e3, self.energy_max * 1e3, step_eV=self.bin_size * 1e3)

    def _filters(self):
        """List of (material, thickness [mm], density [g/cm3]) of the selected filters."""
        return [(getattr(self, "filter_material_%d" % i).strip(), getattr(self, "filter_thickness_%d" % i),
                 filter_density(getattr(self, "filter_material_%d" % i), getattr(self, "filter_density_%d" % i)))
                for i in range(1, self.number_of_filters + 1)]

    def _isotopes_and_activities(self):
        return [(getattr(self, "isotope_%d" % i), getattr(self, "activity_%d" % i))
                for i in range(1, self.number_of_isotopes + 2)]

    def _intensity_title(self):
        return "Intensity [photons/s]" if self.intensity_units == 0 else \
               "Intensity [photons in %g s]" % self.acquisition_time

    def plot_results(self, calculated_data, progressBarValue=80):
        if not self.view_type == 0:
            if not calculated_data is None:
                current_index = self.tabs.currentIndex()

                self.view_type_combo.setEnabled(False)

                lines = calculated_data.get_content("xoppy_data_lines")
                emitted = calculated_data.get_content("xoppy_data_lines_emitted")
                xoppy_data = calculated_data.get_content("xoppy_data")

                try:
                    # tab 0: each emission line as a vertical stick from 0 to its intensity
                    def sticks(data):
                        y = numpy.zeros(3 * data.shape[0])
                        y[1::3] = data[:, 1]
                        return numpy.repeat(data[:, 0] * 1e-3, 3), y
                    title = "Isotopes: %s" % ", ".join([iso for iso, _ in self._isotopes_and_activities()])
                    if self.number_of_filters > 0:
                        title += " (blue: emitted, red: after filters)"
                    x, y = sticks(emitted)
                    self.plot_data1D(x, y, 0, 0, title=title,
                                     xtitle="Photon Energy [keV]", ytitle=self._intensity_title(),
                                     control=False, xlog=False, ylog=False)
                    if self.number_of_filters > 0:
                        x, y = sticks(lines)
                        self.plot_canvas[0].addCurve(x, y, legend="after filters", color="red", replace=False)

                    # tabs 1-3: binned spectrum (standard XOPPY source format)
                    titles, xtitles, ytitles = self.getTitles(), self.getXTitles(), self.getYTitles()
                    for index in range(1, len(titles)):
                        self.plot_histo(xoppy_data[:, 0], xoppy_data[:, index],
                                        progressBarValue + index * (100 - progressBarValue) / len(titles),
                                        tabs_canvas_index=index, plot_canvas_index=index,
                                        title=titles[index], xtitle=xtitles[index], ytitle=ytitles[index])
                except Exception as e:
                    self.view_type_combo.setEnabled(True)
                    raise Exception("Data not plottable: bad content\n" + str(e))

                self.view_type_combo.setEnabled(True)

                try:
                    self.tabs.setCurrentIndex(current_index)
                except:
                    pass
            else:
                raise Exception("Empty Data")

    def update_script(self):
        """Fill the Script tab with the current inputs (no calculation, no network)."""
        try:
            time_factor = 1.0 if self.intensity_units == 0 else self.acquisition_time
            script = self.script_template(self._isotopes_and_activities(), RADIATION_TYPES[self.radiation_type],
                                          time_factor)
        except Exception as e:
            script = "# script not available: %s\n" % str(e)
        self.xoppy_script.set_code(script)
        return script

    def do_xoppy_calculation(self):

        self.update_script()  # current inputs, even if the calculation fails

        if not RADIONUCLIDE_EMISSION_DB_INSTALLED:
            QMessageBox.information(self, "Missing installation", INSTALL_MESSAGE, QMessageBox.StandardButton.Ok)
            return None

        if self.isotope_list_error is not None:
            raise Exception("This widget needs network access.\n" + self.isotope_list_error +
                            "\n\nPlease connect and reopen the widget.")

        isotopes = self._isotopes_and_activities()
        radiation_types = RADIATION_TYPES[self.radiation_type]
        time_factor = 1.0 if self.intensity_units == 0 else self.acquisition_time

        print("MIRDspecs cache directory: %s" % get_mirdspecs_directory())
        print("List of isotopes (%d): %s" % (len(self.isotope_list), self.isotope_list_source))
        print("Spectra used:")

        # emitted spectrum: yields [photons/decay] x activity [Bq] (x acquisition time [s])
        lines = []
        for isotope, activity in isotopes:
            for line in load_isotope(isotope, radiation_types=radiation_types, verbose=True).lines:
                if self.energy_min <= line.energy_keV <= self.energy_max:
                    lines.append(EmissionLine(line.energy_keV, line.yield_per_decay * activity * time_factor,
                                              line.radiation_type, isotope))
        if len(lines) == 0:
            raise Exception("No photon lines found for the selected isotopes, radiation type and energy range")
        lines.sort(key=lambda x: x.energy_keV)

        print("\n%12s  %14s  %-20s %s" % ("Energy[keV]", "Intensity", "Type", "Isotope"))
        for line in lines:
            print("%12.4f  %14.6g  %-20s %s" % (line.energy_keV, line.yield_per_decay, line.radiation_type, line.isotope))

        # lines with the same energy are summed: energy [eV], intensity
        emitted = merge_lines([x.energy_keV * 1e3 for x in lines], [x.yield_per_decay for x in lines])
        print("\nNumber of lines: %d (%d different energies)" % (len(lines), emitted.shape[0]))
        self._print_totals("Total emitted (sum of lines)", emitted, time_factor)

        # internal filters (NIST attenuation from radionuclide-emission-db)
        merged = emitted.copy()
        filters = self._filters()
        if len(filters) > 0:
            print("\nInternal filters (NIST tables cached in %s):" % get_nist_directory())
            material_filters = []
            for material, thickness, density in filters:
                print("  %s  thickness: %g mm  density: %g g/cm3" % (material, thickness, density))
                material_filters.append(get_filter(material, thickness, density, verbose=True))
            transmission = filters_transmission(emitted[:, 0] * 1e-3, material_filters)
            merged[:, 1] *= transmission
            n_removed = (emitted[:, 0] < FILTER_MIN_ENERGY * 1e3).sum()
            if n_removed > 0:
                print("  %d line energies below %g keV (no NIST data) are removed (transmission 0)" % (n_removed, FILTER_MIN_ENERGY))
            print("\n%12s  %14s  %14s  %14s" % ("Energy[keV]", "Emitted", "Transmission", "After filters"))
            for i in range(emitted.shape[0]):
                print("%12.4f  %14.6g  %14.6g  %14.6g" % (emitted[i, 0] * 1e-3, emitted[i, 1], transmission[i], merged[i, 1]))
            print("")
            self._print_totals("Total after filters (sum of lines)", merged, time_factor)
            print("Transmitted fraction: photons: %g, power: %g" % (
                merged[:, 1].sum() / emitted[:, 1].sum(),
                (merged[:, 1] * merged[:, 0]).sum() / (emitted[:, 1] * emitted[:, 0]).sum()))

        # binned spectrum (always per second), standard XOPPY format for POWER
        binned = lines_to_binned_spectrum(merged[:, 0], merged[:, 1] / time_factor,
                                          self._energy_grid())
        step = binned[1, 0] - binned[0, 0]
        density = binned[:, 1] / (1e-3 * binned[:, 0])  # photons/s/eV
        print("\nBinned spectrum: %d points from %g to %g eV, step %g eV" % (binned.shape[0], binned[0, 0],
                                                                              binned[-1, 0], step))
        print("    integrated flux: %g photons/s, integrated power: %g W" % (
            step * (density.sum() - 0.5 * (density[0] + density[-1])), binned[-1, 3]))

        script = self.update_script()

        return merged, binned, script, emitted

    def _print_totals(self, title, lines, time_factor):
        power = (lines[:, 1] * lines[:, 0] * codata.e).sum()  # W (or J in the acquisition time)
        if self.intensity_units == 0:
            print("%s: %g photons/s, power: %g W" % (title, lines[:, 1].sum(), power))
        else:
            print("%s: %g photons, energy: %g J (in %g s)" % (title, lines[:, 1].sum(), power, self.acquisition_time))
            print("%s  %g photons/s, power: %g W" % (" " * len(title), lines[:, 1].sum() / time_factor, power / time_factor))

    def _energy_grid_script(self):
        if self.binning == 0:
            return "energy = numpy.linspace(energy_min * 1e3, energy_max * 1e3, %d)  # eV" % self.number_of_points
        else:
            return ("bin_size = %r  # keV\n"
                    "energy = energy_min * 1e3 + bin_size * 1e3 * numpy.arange(\n"
                    "    max(int(numpy.ceil((energy_max - energy_min) / bin_size - 1e-9)) + 1, 2))  # eV" % self.bin_size)

    def script_template(self, isotopes, radiation_types, time_factor):
        script = """#
# script to make the calculations (created by XOPPY:isotope_spectrum)
#
import numpy
import scipy.constants as codata
from radionuclide_emission_db import Radionuclide, Spectrum, EmissionLine

# network check: list of isotopes from the MIRDspecs index (used by the widget, not needed here)
# import urllib.request; print("proxies:", urllib.request.getproxies())
# from radionuclide_emission_db import available_isotopes; print(len(available_isotopes()), "isotopes")

cache_dir = {cache_dir}  # MIRDspecs CSV files are downloaded here when first used
isotopes = {isotopes}  # (isotope, activity [Bq])
time_factor = {time_factor}  # acquisition time [s] (1 for photons/s)
energy_min, energy_max = {energy_min}, {energy_max}  # keV

lines = []
for isotope, activity in isotopes:
    for line in Radionuclide(isotope, cache_dir=cache_dir).load(radiation_types={radiation_types}).lines:
        if energy_min <= line.energy_keV <= energy_max:
            lines.append(EmissionLine(line.energy_keV, line.yield_per_decay * activity * time_factor,
                                      line.radiation_type, isotope))
lines.sort(key=lambda x: x.energy_keV)
emitted = Spectrum(tuple(lines), label=", ".join([iso for iso, _ in isotopes]))

# internal filters: (material, thickness [mm], density [g/cm3]), NIST tables cached in nist_dir
# (lines below 1 keV are removed by the filters: no NIST data)
from radionuclide_emission_db import material_filter
nist_dir = {nist_dir}
filters = {filters}
for material, thickness, density in filters:
    emitted = emitted.apply_filter(material_filter(material, thickness, density_g_cm3=density,
                                                   attenuation_data_dir=nist_dir))

# lines with the same energy are summed
energies, inverse = numpy.unique([x.energy_keV * 1e3 for x in emitted.lines], return_inverse=True)  # eV
intensity = numpy.zeros(energies.size)
numpy.add.at(intensity, inverse, [x.yield_per_decay for x in emitted.lines])
print("Total: %g photons (/s), power: %g W (or J)" % (intensity.sum(), (intensity * energies * codata.e).sum()))

# binned spectrum on a regular grid (per second): each line is shared between its two neighbouring
# points with linear weights (photons and power preserved); end points doubled (trapezoid rule)
{energy_grid}
step = energy[1] - energy[0]
position = (energies - energy[0]) / step
k = numpy.clip(numpy.floor(position).astype(int), 0, energy.size - 2)
f = position - k
weights = numpy.zeros(energy.size)
numpy.add.at(weights, k, intensity / time_factor * (1 - f))
numpy.add.at(weights, k + 1, intensity / time_factor * f)
density = weights / step  # photons/s/eV
density[[0, -1]] *= 2
flux = density * 1e-3 * energy  # photons/s/0.1%bw
spectral_power = density * energy * codata.e  # W/eV (used by POWER)
cumulated_power = numpy.concatenate(([0.0], numpy.cumsum(0.5 * (spectral_power[1:] + spectral_power[:-1]) * step)))
print("Binned: integrated power: %g W" % cumulated_power[-1])

# plot
if True:
    from srxraylib.plot.gol import plot
    y = numpy.zeros(3 * energies.size)
    y[1::3] = intensity
    plot(numpy.repeat(energies * 1e-3, 3), y,
         xtitle="Photon energy [keV]", ytitle="{ytitle}", grid=1, title="Isotopes: " + emitted.label, show=0)
    plot(energy, flux, xtitle="Photon energy [eV]", ytitle="Flux [Phot/sec/0.1%bw]", grid=1, show=0)
    plot(energy, spectral_power, xtitle="Photon energy [eV]", ytitle="Spectral Power [W/eV]", grid=1, show=0)
    plot(energy, cumulated_power, xtitle="Photon energy [eV]", ytitle="Cumulated Power [W]", grid=1)

#
# end script
#
""".format(isotopes=repr(isotopes),
           cache_dir=repr(get_mirdspecs_directory()),
           radiation_types=repr(radiation_types),
           time_factor=time_factor,
           energy_min=self.energy_min,
           energy_max=self.energy_max,
           energy_grid=self._energy_grid_script(),
           nist_dir=repr(get_nist_directory()),
           filters=repr(self._filters()),
           ytitle=self._intensity_title())
        return script

    def extract_data_from_xoppy_output(self, calculation_output):
        merged, binned, script, emitted = calculation_output

        calculated_data = DataExchangeObject("XOPPY", self.get_data_exchange_widget_name())

        # columns: energy [eV], flux [photons/s/0.1%bw], spectral power [W/eV], cumulated power [W]
        calculated_data.add_content("xoppy_data", binned)
        calculated_data.add_content("xoppy_data_lines", merged)  # columns: energy [eV], intensity (after filters)
        calculated_data.add_content("xoppy_data_lines_emitted", emitted)  # same, before filters
        calculated_data.add_content("xoppy_script", script)

        return calculated_data

    def get_data_exchange_widget_name(self):
        # return "isotope_spectrum"
        return "BLACK_BODY"  # todo change name to "isotope_spectrum" and allow the name in xoppy/power

    def getTitles(self):
        return ['Emission lines', 'Flux', 'Spectral Power', 'Cumulated Power']

    def getXTitles(self):
        return ["Photon Energy [keV]", "Photon Energy [eV]", "Photon Energy [eV]", "Photon Energy [eV]"]

    def getYTitles(self):
        return [self._intensity_title(), "Flux [Phot/sec/0.1%bw]", "Spectral Power [W/eV]", "Cumulated Power [W]"]

    def getVariablesToPlot(self):
        return [(0, 1), (0, 1), (0, 2), (0, 3)]

    def getLogPlot(self):
        return [(False, False)] * 4

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    import sys
    from AnyQt.QtWidgets import QMessageBox, QApplication
    app = QApplication(sys.argv)
    ow = OWisotopeSpectrum()
    ow.show()
    app.exec()
    ow.saveSettings()
