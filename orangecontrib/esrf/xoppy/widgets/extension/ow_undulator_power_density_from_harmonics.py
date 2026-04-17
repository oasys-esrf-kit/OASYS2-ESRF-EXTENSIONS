import numpy
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input

from oasys2.widget import gui as oasysgui
from oasys2.widget.util.exchange import DataExchangeObject
from oasys2.widget.util import congruence
from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

from orangecontrib.xoppy.widgets.gui.ow_xoppy_widget import XoppyWidget
from xoppylib.sources.xoppy_undulators import xoppy_calc_undulator_power_density_from_harmonics

from syned.widget.widget_decorator import WidgetDecorator
import syned.beamline.beamline as synedb
import syned.storage_ring.magnetic_structures.insertion_device as synedid


class OWundulator_power_density_from_harmonics(XoppyWidget, WidgetDecorator):
    name = "Undulator Power Density From Harmonics"
    id = "orange.widgets.dataundulator_power_density_from_harmonics"
    description = "Undulator Power Density From harmonics"
    icon = "icons/xoppy_undulator_power_density.png"
    priority = 3.1
    category = ""
    keywords = ["xoppy", "undulator_power_density_from_harmonics"]

    USEEMITTANCES           = Setting(1)
    ELECTRONENERGY          = Setting(6.04)
    ELECTRONENERGYSPREAD    = Setting(0.001)
    ELECTRONCURRENT         = Setting(0.2)
    ELECTRONBEAMSIZEH       = Setting(0.000395)
    ELECTRONBEAMSIZEV       = Setting(9.9e-06)
    ELECTRONBEAMDIVERGENCEH = Setting(1.05e-05)
    ELECTRONBEAMDIVERGENCEV = Setting(3.9e-06)
    PERIODID                = Setting(0.018)
    NPERIODS                = Setting(222)
    KV                      = Setting(1.68)
    KH                      = Setting(0.0)
    KPHASE                  = Setting(0.0)
    DISTANCE                = Setting(30.0)
    GAPH                    = Setting(0.01)
    GAPV                    = Setting(0.01)
    HSLITPOINTS             = Setting(41)
    VSLITPOINTS             = Setting(41)
    METHOD                  = Setting(0)
    harmonic_max            = Setting(20)
    MASK_FLAG               = Setting(0)
    MASK_ROT_H_DEG          = Setting(0.0)
    MASK_ROT_V_DEG          = Setting(0.0)
    MASK_H_MIN              = Setting(-1000.0)
    MASK_H_MAX              = Setting( 1000.0)
    MASK_V_MIN              = Setting(-1000.0)
    MASK_V_MAX              = Setting( 1000.0)
    H5_FILE_DUMP            = Setting(0)
    photon_energy_bin       = Setting(100)

    class Inputs:
        syned_data = WidgetDecorator.syned_input_data()

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
        gui.comboBox(box1, self, "USEEMITTANCES", label=self.unitLabels()[idx],
                    items=['No', 'Yes'], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #widget index 0 
        idx += 1 
        box1 = gui.widgetBox(box) 

        self.id_ELECTRONENERGY = oasysgui.lineEdit(box1, self, "ELECTRONENERGY",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)

        self.show_at(self.unitFlags()[idx], box1)
        
        #widget index 1 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_ELECTRONENERGYSPREAD = oasysgui.lineEdit(box1, self, "ELECTRONENERGYSPREAD",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 2 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_ELECTRONCURRENT = oasysgui.lineEdit(box1, self, "ELECTRONCURRENT",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 3 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_ELECTRONBEAMSIZEH = oasysgui.lineEdit(box1, self, "ELECTRONBEAMSIZEH",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 4 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_ELECTRONBEAMSIZEV = oasysgui.lineEdit(box1, self, "ELECTRONBEAMSIZEV",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 5 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_ELECTRONBEAMDIVERGENCEH = oasysgui.lineEdit(box1, self, "ELECTRONBEAMDIVERGENCEH",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 6 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_ELECTRONBEAMDIVERGENCEV = oasysgui.lineEdit(box1, self, "ELECTRONBEAMDIVERGENCEV",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 7 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_PERIODID = oasysgui.lineEdit(box1, self, "PERIODID",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 8 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_NPERIODS = oasysgui.lineEdit(box1, self, "NPERIODS",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 9 
        idx += 1 
        box1 = gui.widgetBox(box) 
        self.id_KV = oasysgui.lineEdit(box1, self, "KV",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 

        #widget index 9 B
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_KH = oasysgui.lineEdit(box1, self, "KH",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 9 C
        idx += 1
        box1 = gui.widgetBox(box)
        self.id_KPHASE = oasysgui.lineEdit(box1, self, "KPHASE",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #widget index 10 
        idx += 1 
        box1 = gui.widgetBox(box) 
        oasysgui.lineEdit(box1, self, "DISTANCE",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 11 
        idx += 1 
        box1 = gui.widgetBox(box) 
        oasysgui.lineEdit(box1, self, "GAPH",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 12 
        idx += 1 
        box1 = gui.widgetBox(box) 
        oasysgui.lineEdit(box1, self, "GAPV",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 13 
        idx += 1 
        box1 = gui.widgetBox(box) 
        oasysgui.lineEdit(box1, self, "HSLITPOINTS",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 14 
        idx += 1 
        box1 = gui.widgetBox(box) 
        oasysgui.lineEdit(box1, self, "VSLITPOINTS",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 
        
        #widget index 15 
        idx += 1 
        box1 = gui.widgetBox(box) 
        gui.comboBox(box1, self, "METHOD", label=self.unitLabels()[idx],
                     items=['URGENT (fortran)', 'URGENTPY (python)'], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1) 

        #widget index ***
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "harmonic_max",
                     label=self.unitLabels()[idx],
                    valueType=int, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #
        # Mask
        #

        #widget index 16
        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "MASK_FLAG", label=self.unitLabels()[idx],
                    items=['No', 'Yes'], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


        #widget index 17
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "MASK_ROT_H_DEG",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 18
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "MASK_ROT_V_DEG",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 19
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "MASK_H_MIN",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 20
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "MASK_H_MAX",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 21
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "MASK_V_MIN",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 22
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "MASK_V_MAX",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index 23
        idx += 1
        box1 = gui.widgetBox(box)
        gui.comboBox(box1, self, "H5_FILE_DUMP", label=self.unitLabels()[idx],
                    items=['No', 'Yes: undulator_power_density_from_harmonics.h5'], orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)

        #widget index **
        idx += 1
        box1 = gui.widgetBox(box)
        oasysgui.lineEdit(box1, self, "photon_energy_bin",
                     label=self.unitLabels()[idx],
                    valueType=float, orientation="horizontal", labelWidth=250)
        self.show_at(self.unitFlags()[idx], box1)


    def unitLabels(self):
         return ["Use emittances","Electron Energy [GeV]", "Electron Energy Spread", "Electron Current [A]",\
                 "Electron Beam Size H [m]", "Electron Beam Size V [m]", "Electron Beam Divergence H [rad]", "Electron Beam Divergence V [rad]", \
                 "Period ID [m]", "Number of periods", "Kv [K value vertical field]", \
                 "Kh [K value horizontal field]","Kphase [Phase diff Kh-Kv in rad]",\
                 "Distance to slit [m]", "Slit gap H [m]", "Slit gap V [m]", "Number of slit mesh points in H", "Number of slit mesh points in V",\
                 "calculation code","number of harmonics",\
                 "modify slit","Rotation around H axis [deg]","Rotation around V axis [deg]","Mask H min [mm]","Mask H max [mm]",'Mask V min [mm]',"Mask V max [mm]",\
                 "Dump hdf5 file",
                 "Energy bin [eV] (for Spectral Power)"]

    def unitFlags(self):
         return ["True","True", "self.USEEMITTANCES == 1 and self.METHOD != 1", "True",\
                 "self.USEEMITTANCES == 1", "self.USEEMITTANCES == 1", "self.USEEMITTANCES == 1", "self.USEEMITTANCES == 1", \
                 "True", "True", "True",\
                 "self.METHOD != 0","self.METHOD != 0",\
                 "True", "True", "True", "True", "True",\
                 "True","True",\
                 "True","self.MASK_FLAG == 1","self.MASK_FLAG == 1","self.MASK_FLAG == 1","self.MASK_FLAG == 1","self.MASK_FLAG == 1","self.MASK_FLAG == 1",\
                 "True",
                 "True"]

    def get_help_name(self):
        return 'undulator_power_density'

    def check_fields(self):

        self.ELECTRONENERGY = congruence.checkStrictlyPositiveNumber(self.ELECTRONENERGY, "Electron Energy")
        if not self.METHOD == 1: self.ELECTRONENERGYSPREAD = congruence.checkPositiveNumber(self.ELECTRONENERGYSPREAD, "Electron Energy Spread")
        self.ELECTRONCURRENT = congruence.checkStrictlyPositiveNumber(self.ELECTRONCURRENT, "Electron Current")
        self.ELECTRONBEAMSIZEH = congruence.checkPositiveNumber(self.ELECTRONBEAMSIZEH, "Electron Beam Size H")
        self.ELECTRONBEAMSIZEV = congruence.checkPositiveNumber(self.ELECTRONBEAMSIZEV, "Electron Beam Size V")
        self.ELECTRONBEAMDIVERGENCEH = congruence.checkPositiveNumber(self.ELECTRONBEAMDIVERGENCEH, "Electron Beam Divergence H")
        self.ELECTRONBEAMDIVERGENCEV = congruence.checkPositiveNumber(self.ELECTRONBEAMDIVERGENCEV, "Electron Beam Divergence V")
        self.PERIODID = congruence.checkStrictlyPositiveNumber(self.PERIODID, "Period ID")
        self.NPERIODS = congruence.checkStrictlyPositiveNumber(self.NPERIODS, "Number of Periods")
        self.KV = congruence.checkPositiveNumber(self.KV, "Kv")
        self.KH = congruence.checkPositiveNumber(self.KH, "Kh")
        self.KPHASE = congruence.checkNumber(self.KPHASE, "Kphase")
        self.DISTANCE = congruence.checkPositiveNumber(self.DISTANCE, "Distance to slit")
        self.GAPH = congruence.checkPositiveNumber(self.GAPH, "Slit gap H")
        self.GAPV = congruence.checkPositiveNumber(self.GAPV, "Slit gap V")
        self.HSLITPOINTS = congruence.checkStrictlyPositiveNumber(self.HSLITPOINTS, "Number of slit mesh points in H")
        self.VSLITPOINTS = congruence.checkStrictlyPositiveNumber(self.VSLITPOINTS, "Number of slit mesh points in V")

        if  self.METHOD == 1: # URGENT
            congruence.checkLessOrEqualThan(self.HSLITPOINTS, 51, "Number of slit mesh points for URGENT "," 51")
            congruence.checkLessOrEqualThan(self.VSLITPOINTS, 51, "Number of slit mesh points for URGENT "," 51")


    def plot_results(self, calculated_data, progressBarValue=80):
        if not self.view_type == 0:
            if not calculated_data is None:

                self.initializeTabs() # added by srio to avoid overlapping graphs

                self.view_type_combo.setEnabled(False)

                data = calculated_data.get_content("xoppy_data")
                code = calculated_data.get_content("xoppy_code")

                h = data[0]
                v = data[1]
                p = data[2]
                p_harmonics = data[3]
                e_harmonics = data[4]

                try:

                    print("\nResult arrays (shapes): ", h.shape, v.shape, p.shape )

                    # tab 0 Power density
                    self.plot_data2D(p, h, v, 0, 0,
                                     xtitle='H [mm]',
                                     ytitle='V [mm]',
                                     title='Code '+code+'; Power density [W/mm^2]')
                    # tab 1 Power density per harmonic
                    s = p_harmonics.shape
                    self.plot_data3D(p_harmonics, numpy.arange(s[0]), h, v, 1, 0,
                                    title="harmonic", xtitle="H [mm]", ytitle="V [mm]", color_limits_uniform=False,
                                     title_callback=lambda idx: "harmonic: %d (index: %d) " % (idx+1, idx))

                    # tab 2 Spectral Power

                    energies = e_harmonics.flatten()  # Flatten all energy values
                    powers = p_harmonics.flatten() * (h[1] - h[0]) * (v[1] - v[0])  # Flatten corresponding power contributions

                    # Define bins
                    de = self.photon_energy_bin  # eV
                    e_bins = numpy.arange(energies.min(), energies.max() + de, de)
                    print("Spectrum calculated from histogramming in photon energy: min max delta. n_bins: ",
                          energies.min(), energies.max(), de, e_bins.size)

                    # Bin the powers into energy bins
                    power_vs_energy, bin_edges = numpy.histogram(energies, bins=e_bins, weights=powers)
                    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

                    self.plot_data1D(bin_centers, power_vs_energy / de, 2, 0, title="Spectral Power",
                                     xtitle="Photon Energy [eV]", ytitle="Spectral Power [W/eV]",
                                     control=False, xlog=False, ylog=False)

                    # tab 3 Cumulated power
                    self.plot_data1D(bin_centers, power_vs_energy.cumsum(), 3, 0, title="Spectral Power",
                                     xtitle="Photon Energy [eV]", ytitle="Cumulated Power [W]",
                                     control=False, xlog=False, ylog=False)

                except Exception as e:
                    self.view_type_combo.setEnabled(True)

                    raise Exception("Data not plottable: bad content\n" + str(e))

                self.view_type_combo.setEnabled(True)
            else:
                raise Exception("Empty Data")

    def do_xoppy_calculation(self):
        if self.H5_FILE_DUMP == 0:
            h5_file = ""
        else:
            h5_file = "undulator_power_density_from_harmonics.h5"

        h5_parameters = {
            "ELECTRONENERGY":self.ELECTRONENERGY,
            "ELECTRONENERGYSPREAD":self.ELECTRONENERGYSPREAD,
            "ELECTRONCURRENT":self.ELECTRONCURRENT,
            "ELECTRONBEAMSIZEH":self.ELECTRONBEAMSIZEH,
            "ELECTRONBEAMSIZEV":self.ELECTRONBEAMSIZEV,
            "ELECTRONBEAMDIVERGENCEH":self.ELECTRONBEAMDIVERGENCEH,
            "ELECTRONBEAMDIVERGENCEV":self.ELECTRONBEAMDIVERGENCEV,
            "PERIODID":self.PERIODID,
            "NPERIODS":self.NPERIODS,
            "KV":self.KV,
            "KH": self.KH,
            "KPHASE": self.KPHASE,
            "DISTANCE":self.DISTANCE,
            "GAPH":self.GAPH,
            "GAPV":self.GAPV,
            "HSLITPOINTS":self.HSLITPOINTS,
            "VSLITPOINTS":self.VSLITPOINTS,
            "METHOD":self.METHOD,
            "USEEMITTANCES":self.USEEMITTANCES,
            "MASK_FLAG":self.MASK_FLAG,
            "MASK_ROT_H_DEG":self.MASK_ROT_H_DEG,
            "MASK_ROT_V_DEG":self.MASK_ROT_V_DEG,
            "MASK_H_MIN":self.MASK_H_MIN,
            "MASK_H_MAX":self.MASK_H_MAX,
            "MASK_V_MIN":self.MASK_V_MIN,
            "MASK_V_MAX":self.MASK_V_MAX,
            "harmonic_max": self.harmonic_max,
            "photon_energy_bin": self.photon_energy_bin,
        }

        script = self.script_template().format_map(h5_parameters)
        self.xoppy_script.set_code(script)

        h, v, p, code, power_density_harmonics, energy_harmonics, spectral_power, spectral_power_energy =  \
            xoppy_calc_undulator_power_density_from_harmonics(
                                                   ELECTRONENERGY=self.ELECTRONENERGY,
                                                   ELECTRONENERGYSPREAD=self.ELECTRONENERGYSPREAD,
                                                   ELECTRONCURRENT=self.ELECTRONCURRENT,
                                                   ELECTRONBEAMSIZEH=self.ELECTRONBEAMSIZEH,
                                                   ELECTRONBEAMSIZEV=self.ELECTRONBEAMSIZEV,
                                                   ELECTRONBEAMDIVERGENCEH=self.ELECTRONBEAMDIVERGENCEH,
                                                   ELECTRONBEAMDIVERGENCEV=self.ELECTRONBEAMDIVERGENCEV,
                                                   PERIODID=self.PERIODID,
                                                   NPERIODS=self.NPERIODS,
                                                   KV=self.KV,
                                                   KH=self.KH,
                                                   KPHASE=self.KPHASE,
                                                   DISTANCE=self.DISTANCE,
                                                   GAPH=self.GAPH,
                                                   GAPV=self.GAPV,
                                                   HSLITPOINTS=self.HSLITPOINTS,
                                                   VSLITPOINTS=self.VSLITPOINTS,
                                                   METHOD=self.METHOD,
                                                   USEEMITTANCES=self.USEEMITTANCES,
                                                   MASK_FLAG=self.MASK_FLAG,
                                                   MASK_ROT_H_DEG=self.MASK_ROT_H_DEG,
                                                   MASK_ROT_V_DEG=self.MASK_ROT_V_DEG,
                                                   MASK_H_MIN=self.MASK_H_MIN,
                                                   MASK_H_MAX=self.MASK_H_MAX,
                                                   MASK_V_MIN=self.MASK_V_MIN,
                                                   MASK_V_MAX=self.MASK_V_MAX,
                                                   h5_file=h5_file,
                                                   h5_entry_name="XOPPY_POWERDENSITY_FROM_HARMONICS",
                                                   h5_initialize=True,
                                                   h5_parameters=h5_parameters,
                                                   harmonic_max=self.harmonic_max,
                                                   photon_energy_bin=self.photon_energy_bin,
                                                   )

        return h, v, p, code, script, power_density_harmonics, energy_harmonics, spectral_power, spectral_power_energy

    def script_template(self):
        return """
#
# script to make the calculations (created by XOPPY:undulator_spectrum)
#
from xoppylib.sources.xoppy_undulators import xoppy_calc_undulator_power_density_from_harmonics

# define inputs here to be written in h5 file
h5_parameters = dict()
h5_parameters["ELECTRONENERGY"]=           {ELECTRONENERGY}
h5_parameters["ELECTRONENERGYSPREAD"]=     {ELECTRONENERGYSPREAD}
h5_parameters["ELECTRONCURRENT"]=          {ELECTRONCURRENT}
h5_parameters["ELECTRONBEAMSIZEH"]=        {ELECTRONBEAMSIZEH}
h5_parameters["ELECTRONBEAMSIZEV"]=        {ELECTRONBEAMSIZEV}
h5_parameters["ELECTRONBEAMDIVERGENCEH"]=  {ELECTRONBEAMDIVERGENCEH}
h5_parameters["ELECTRONBEAMDIVERGENCEV"]=  {ELECTRONBEAMDIVERGENCEV}
h5_parameters["PERIODID"]=                 {PERIODID}
h5_parameters["NPERIODS"]=                 {NPERIODS}
h5_parameters["KV"]=                       {KV}
h5_parameters["KH"]=                       {KH}
h5_parameters["KPHASE"]=                   {KPHASE}
h5_parameters["DISTANCE"]=                 {DISTANCE}
h5_parameters["GAPH"]=                     {GAPH}
h5_parameters["GAPV"]=                     {GAPV}
h5_parameters["HSLITPOINTS"]=              {HSLITPOINTS}
h5_parameters["VSLITPOINTS"]=              {VSLITPOINTS}
h5_parameters["METHOD"]=                   {METHOD}  # 0=urgent (fortran), 1=urgentpy (python)
h5_parameters["USEEMITTANCES"]=            {USEEMITTANCES}
h5_parameters["MASK_FLAG"]=                {MASK_FLAG}
h5_parameters["MASK_ROT_H_DEG"]=           {MASK_ROT_H_DEG}
h5_parameters["MASK_ROT_V_DEG"]=           {MASK_ROT_V_DEG}
h5_parameters["MASK_H_MIN"]=               {MASK_H_MIN}
h5_parameters["MASK_H_MAX"]=               {MASK_H_MAX}
h5_parameters["MASK_V_MIN"]=               {MASK_V_MIN}
h5_parameters["MASK_V_MAX"]=               {MASK_V_MAX}
h5_parameters["harmonic_max"]=             {harmonic_max}  # maximum harmonic to calculate
h5_parameters["photon_energy_bin"]=        {photon_energy_bin}  # in eV, for calculating Spectral Power

        
h, v, power_density, code, power_density_harmonics, energy_harmonics, spectral_power, spectral_power_energy = \
    xoppy_calc_undulator_power_density_from_harmonics(
    ELECTRONENERGY           =  h5_parameters["ELECTRONENERGY"],
    ELECTRONENERGYSPREAD     =  h5_parameters["ELECTRONENERGYSPREAD"],
    ELECTRONCURRENT          =  h5_parameters["ELECTRONCURRENT"],
    ELECTRONBEAMSIZEH        =  h5_parameters["ELECTRONBEAMSIZEH"],
    ELECTRONBEAMSIZEV        =  h5_parameters["ELECTRONBEAMSIZEV"],
    ELECTRONBEAMDIVERGENCEH  =  h5_parameters["ELECTRONBEAMDIVERGENCEH"],
    ELECTRONBEAMDIVERGENCEV  =  h5_parameters["ELECTRONBEAMDIVERGENCEV"],
    PERIODID                 =  h5_parameters["PERIODID"],
    NPERIODS                 =  h5_parameters["NPERIODS"],
    KV                       =  h5_parameters["KV"],
    KH                       =  h5_parameters["KH"],
    KPHASE                   =  h5_parameters["KPHASE"],
    DISTANCE                 =  h5_parameters["DISTANCE"],
    GAPH                     =  h5_parameters["GAPH"],
    GAPV                     =  h5_parameters["GAPV"],
    HSLITPOINTS              =  h5_parameters["HSLITPOINTS"],
    VSLITPOINTS              =  h5_parameters["VSLITPOINTS"],
    METHOD                   =  h5_parameters["METHOD"],
    harmonic_max             =  h5_parameters["harmonic_max"],
    USEEMITTANCES            =  h5_parameters["USEEMITTANCES"],
    MASK_FLAG                =  h5_parameters["MASK_FLAG"],
    MASK_ROT_H_DEG           =  h5_parameters["MASK_ROT_H_DEG"],
    MASK_ROT_V_DEG           =  h5_parameters["MASK_ROT_V_DEG"],
    MASK_H_MIN               =  h5_parameters["MASK_H_MIN"],
    MASK_H_MAX               =  h5_parameters["MASK_H_MAX"],
    MASK_V_MIN               =  h5_parameters["MASK_V_MIN"],
    MASK_V_MAX               =  h5_parameters["MASK_V_MAX"],
    h5_file                  =  "undulator_power_density_from_harmonics.h5",
    h5_entry_name            =  "XOPPY_POWERDENSITY_FROM_HARMONICS",
    h5_initialize            =  True,
    h5_parameters            =  h5_parameters,
    photon_energy_bin        =  h5_parameters["photon_energy_bin"],
    )
    
# example plot
if True:
    # Power Density
    from srxraylib.plot.gol import plot, plot_image
    plot_image(power_density_harmonics.sum(axis=0), h, v, xtitle="H [mm]", ytitle="V [mm]", title="Power density W/mm2")

    # Spectral Power & Cumulated Power
    plot(spectral_power_energy, spectral_power, xtitle="Photon energy [eV]",
         ytitle="Spectral Power [W/eV]", grid=1,
         title="Spectral Power (bin: %.3f eV)" % (h5_parameters['photon_energy_bin']))                    
    de = spectral_power_energy[1] - spectral_power_energy[0]
    plot(spectral_power_energy, (spectral_power * de).cumsum(), xtitle="Photon energy [eV]",
         ytitle="Cumulated Power [W]", grid=1,
         title="Cumulated Power (bin: %.3f eV)" % (h5_parameters['photon_energy_bin']))                    

#
# end script
#
"""


    def extract_data_from_xoppy_output(self, calculation_output):
        h, v, p, code, script, p_harmonics, e_harmonics, spectral_power, spectral_power_energy = calculation_output

        calculated_data = DataExchangeObject("XOPPY", self.get_data_exchange_widget_name())

        calculated_data.add_content("xoppy_data", [h, v, p, p_harmonics, e_harmonics, spectral_power, spectral_power_energy])
        calculated_data.add_content("xoppy_code",  code)
        calculated_data.add_content("xoppy_script", script)

        return calculated_data

    def get_data_exchange_widget_name(self):
        return "UNDULATOR_POWER_DENSITY_FROM_HARMONICS"

    def getTitles(self):
        return ['Undulator Power Density', 'Harmonics Power Density', 'Spectral Power', 'Cumulated Power']

    @Inputs.syned_data
    def receive_syned_data(self, data):
        if isinstance(data, synedb.Beamline):
            if not data._light_source is None and isinstance(data._light_source._magnetic_structure, synedid.InsertionDevice):
                light_source = data._light_source

                self.ELECTRONENERGY = light_source._electron_beam._energy_in_GeV
                self.ELECTRONENERGYSPREAD = light_source._electron_beam._energy_spread
                self.ELECTRONCURRENT = light_source._electron_beam._current

                x, xp, y, yp = light_source._electron_beam.get_sigmas_all()

                self.ELECTRONBEAMSIZEH = x
                self.ELECTRONBEAMSIZEV = y
                self.ELECTRONBEAMDIVERGENCEH = xp
                self.ELECTRONBEAMDIVERGENCEV = yp
                self.PERIODID = light_source._magnetic_structure._period_length
                self.NPERIODS = int(light_source._magnetic_structure._number_of_periods)
                self.KV = light_source._magnetic_structure._K_vertical
                self.KH = light_source._magnetic_structure._K_horizontal
                # TODO self.KPHASE = light_source._magnetic_structure._K_vertical

                self.set_enabled(False)

            else:
                self.set_enabled(True)
                # raise ValueError("Syned data not correct")
        else:
            self.set_enabled(True)
            # raise ValueError("Syned data not correct")

    def set_enabled(self,value):
        if value == True:
                self.id_ELECTRONENERGY.setEnabled(True)
                self.id_ELECTRONENERGYSPREAD.setEnabled(True)
                self.id_ELECTRONBEAMSIZEH.setEnabled(True)
                self.id_ELECTRONBEAMSIZEV.setEnabled(True)
                self.id_ELECTRONBEAMDIVERGENCEH.setEnabled(True)
                self.id_ELECTRONBEAMDIVERGENCEV.setEnabled(True)
                self.id_ELECTRONCURRENT.setEnabled(True)
                self.id_PERIODID.setEnabled(True)
                self.id_NPERIODS.setEnabled(True)
                self.id_KV.setEnabled(True)
                self.id_KH.setEnabled(True)
                self.id_KPHASE.setEnabled(True)
        else:
                self.id_ELECTRONENERGY.setEnabled(False)
                self.id_ELECTRONENERGYSPREAD.setEnabled(False)
                self.id_ELECTRONBEAMSIZEH.setEnabled(False)
                self.id_ELECTRONBEAMSIZEV.setEnabled(False)
                self.id_ELECTRONBEAMDIVERGENCEH.setEnabled(False)
                self.id_ELECTRONBEAMDIVERGENCEV.setEnabled(False)
                self.id_ELECTRONCURRENT.setEnabled(False)
                self.id_PERIODID.setEnabled(False)
                self.id_NPERIODS.setEnabled(False)
                self.id_KV.setEnabled(False)
                self.id_KH.setEnabled(False)
                self.id_KPHASE.setEnabled(False)

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    import sys
    from AnyQt.QtWidgets import QMessageBox, QApplication
    app = QApplication(sys.argv)
    ow = OWundulator_power_density_from_harmonics()
    ow.show()
    app.exec()
    ow.saveSettings()