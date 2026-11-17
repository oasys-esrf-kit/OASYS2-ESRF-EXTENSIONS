import os
import tempfile

import numpy
from AnyQt.QtWidgets import QMessageBox
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input

from dabax.dabax_files import dabax_crosssec_files, dabax_f1f2_files
from dabax.dabax_xraylib import DabaxXraylib

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence
from oasys2.widget.util.widget_util import write_surface_file
from oasys2.widget.util.widget_objects import OasysThicknessErrorsData

from syned.beamline.element_coordinates import ElementCoordinates
from syned.beamline.shape import Ellipse, Rectangle

from orangecontrib.shadow4.util.shadow4_objects import PreReflPreProcessorData
from orangecontrib.shadow4.util.shadow4_util import ShadowCongruence, ShadowPhysics, ShadowPlot
from orangecontrib.shadow4.widgets.gui.ow_optical_element import (
    NO_FILE_SPECIFIED,
    OWOpticalElement,
    SUBTAB_INNER_BOX_WIDTH,
)
from orangecontrib.shadow4.widgets.gui.ow_optical_element_with_surface_shape import (
    ShowImageErrorDataFileDialog,
    ShowSurfaceErrorDataFileDialog,
)

from shadow4.beamline.optical_elements.phase_deflectors.s4_numerical_mesh_phase_deflector import (
    S4NumericalMeshPhaseDeflector,
    S4NumericalMeshPhaseDeflectorElement,
)

XRAYLIB_AVAILABLE = True

try:
    import xraylib  # noqa: F401
except Exception:
    XRAYLIB_AVAILABLE = False


class OWPhaseDeflector(OWOpticalElement):
    name = "Phase Deflector"
    description = "Shadow4 phase deflector element"
    icon = "icons/phase_deflector.png"
    priority = 3
    keywords = ["barc", "shadow4", "phase", "deflector", "thickness"]

    class Inputs:
        shadow_data = OWOpticalElement.Inputs.shadow_data
        trigger = OWOpticalElement.Inputs.trigger
        syned_data = OWOpticalElement.Inputs.syned_data
        thickness_errors_data = Input(
            "Thickness Errors Data",
            OasysThicknessErrorsData,
            default=True,
            auto_summary=False,
        )
        prerefl_preprocessor_data = Input(
            "PreRefl PreProcessor Data",
            PreReflPreProcessorData,
            default=True,
            auto_summary=False,
        )

    surface_data_file = Setting(NO_FILE_SPECIFIED)
    thickness_scaling = Setting(1.0)
    coordinate_scaling = Setting(1.0)
    invert_surface = Setting(0)
    shift_thickness_to_zero = Setting(0)
    apply_to_lost = Setting(1)

    aperturing = Setting(0)
    aperture_shape = Setting(1)
    slit_width_xaxis = Setting(0.0)
    slit_height_zaxis = Setting(0.0)
    slit_center_xaxis = Setting(0.0)
    slit_center_zaxis = Setting(0.0)

    ri_calculation_mode = Setting(0)
    prerefl_file = Setting("<none>")
    refraction_index = Setting(1.0)
    attenuation_coefficient = Setting(0.0)
    material = Setting("Be")
    density = Setting(1.484)

    DABAX_F1F2_FILE_INDEX = Setting(0)
    DABAX_CROSSSEC_FILE_INDEX = Setting(0)

    def __init__(self):
        super().__init__(has_footprint=True, show_tab_advanced_settings=True)
        self.set_aperturing(is_init=True)
        self.set_ri_calculation_mode()

    def populate_tab_position(self, tab_position):
        self.orientation_box = oasysgui.widgetBox(
            tab_position,
            "Optical Element Orientation",
            addSpace=True,
            orientation="vertical",
        )

        oasysgui.lineEdit(
            self.orientation_box,
            self,
            "source_plane_distance",
            "Source Plane Distance [m]",
            labelWidth=260,
            valueType=float,
            orientation="horizontal",
            tooltip="source_plane_distance",
        )
        oasysgui.lineEdit(
            self.orientation_box,
            self,
            "image_plane_distance",
            "Image Plane Distance [m]",
            labelWidth=260,
            valueType=float,
            orientation="horizontal",
            tooltip="image_plane_distance",
        )

    def create_basic_settings_subtabs(self, tabs_basic_settings):
        subtab_map = oasysgui.createTabPage(tabs_basic_settings, "Thickness Map")
        subtab_aperture = oasysgui.createTabPage(tabs_basic_settings, "Aperture")
        subtab_material = oasysgui.createTabPage(tabs_basic_settings, "Material")
        return subtab_map, subtab_aperture, subtab_material

    def create_advanced_settings_subtabs(self, tabs_advanced_settings):
        return [oasysgui.createTabPage(tabs_advanced_settings, name="DABAX")]

    def populate_basic_setting_subtabs(self, basic_setting_subtabs):
        subtab_map, subtab_aperture, subtab_material = basic_setting_subtabs
        self.populate_tab_thickness_map(subtab_map)
        self.populate_tab_aperture(subtab_aperture)
        self.populate_tab_material(subtab_material)

    def populate_advanced_setting_subtabs(self, advanced_setting_subtabs):
        self.dabax_box = gui.widgetBox(advanced_setting_subtabs[0], "DABAX Materials Files")
        gui.comboBox(
            self.dabax_box,
            self,
            "DABAX_F1F2_FILE_INDEX",
            tooltip="DABAX_F1F2_FILE_INDEX",
            items=dabax_f1f2_files(),
            label="f1f2 file",
            addSpace=True,
            orientation="horizontal",
        )
        gui.comboBox(
            self.dabax_box,
            self,
            "DABAX_CROSSSEC_FILE_INDEX",
            tooltip="DABAX_CROSSSEC_FILE_INDEX",
            items=dabax_crosssec_files(),
            label="CrossSec file",
            addSpace=True,
            orientation="horizontal",
        )

    def populate_tab_thickness_map(self, tab):
        box = oasysgui.widgetBox(
            tab,
            "Projected Thickness Map",
            addSpace=False,
            orientation="vertical",
            width=SUBTAB_INNER_BOX_WIDTH,
        )

        file_box = oasysgui.widgetBox(box, "", addSpace=True, orientation="horizontal")
        self.le_surface_data_file = oasysgui.lineEdit(
            file_box,
            self,
            "surface_data_file",
            "File",
            tooltip="surface_data_file",
            labelWidth=50,
            valueType=str,
            orientation="horizontal",
        )
        gui.button(file_box, self, "...", callback=self.select_surface_data_file, width=30)
        gui.button(
            file_box,
            self,
            "View Surf",
            callback=self.view_surface_data_file,
            width=65,
            tooltip="Render data in surface mode [slow]",
        )
        gui.button(
            file_box,
            self,
            "View Img",
            callback=self.view_image_data_file,
            width=65,
            tooltip="Render data in image mode [slow]",
        )
        oasysgui.lineEdit(
            box, self, "thickness_scaling", "Thickness scaling",
            tooltip="thickness_scaling", labelWidth=250, valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            box, self, "coordinate_scaling", "Coordinate scaling",
            tooltip="coordinate_scaling", labelWidth=250, valueType=float,
            orientation="horizontal",
        )
        gui.comboBox(
            box, self, "invert_surface", label="Invert surface",
            labelWidth=250, items=["No", "Yes"], sendSelectedValue=False,
            orientation="horizontal", tooltip="invert_surface",
        )

        gui.comboBox(
            box,
            self,
            "shift_thickness_to_zero",
            label="Shift thickness to zero",
            labelWidth=250,
            items=["No", "Yes"],
            sendSelectedValue=False,
            orientation="horizontal",
            tooltip="shift_thickness_to_zero",
        )
        gui.comboBox(
            box,
            self,
            "apply_to_lost",
            label="Apply to lost rays",
            labelWidth=250,
            items=["No", "Yes"],
            sendSelectedValue=False,
            orientation="horizontal",
            tooltip="apply_to_lost",
        )

    def populate_tab_aperture(self, tab):
        box = oasysgui.widgetBox(
            tab,
            "Aperture",
            addSpace=False,
            orientation="vertical",
            width=SUBTAB_INNER_BOX_WIDTH,
        )

        gui.comboBox(
            box,
            self,
            "aperturing",
            label="Aperturing",
            labelWidth=250,
            items=["No", "Yes"],
            callback=self.set_aperturing,
            sendSelectedValue=False,
            orientation="horizontal",
            tooltip="aperturing",
        )

        self.box_aperturing_shape = oasysgui.widgetBox(box, "", addSpace=False, orientation="vertical")
        gui.comboBox(
            self.box_aperturing_shape,
            self,
            "aperture_shape",
            label="Aperture shape",
            labelWidth=250,
            items=["Rectangular", "Ellipse"],
            sendSelectedValue=False,
            orientation="horizontal",
            tooltip="aperture_shape",
        )
        oasysgui.lineEdit(
            self.box_aperturing_shape,
            self,
            "slit_width_xaxis",
            "Width/x-axis [m]",
            tooltip="slit_width_xaxis",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.box_aperturing_shape,
            self,
            "slit_height_zaxis",
            "Height/z-axis [m]",
            tooltip="slit_height_zaxis",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.box_aperturing_shape,
            self,
            "slit_center_xaxis",
            "Center/x-axis [m]",
            tooltip="slit_center_xaxis",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.box_aperturing_shape,
            self,
            "slit_center_zaxis",
            "Center/z-axis [m]",
            tooltip="slit_center_zaxis",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )

    def populate_tab_material(self, tab):
        box = oasysgui.widgetBox(
            tab,
            "Optical Constants",
            addSpace=False,
            orientation="vertical",
            width=SUBTAB_INNER_BOX_WIDTH,
        )

        gui.comboBox(
            box,
            self,
            "ri_calculation_mode",
            label="Calculation mode",
            labelWidth=250,
            items=[
                "User Parameters",
                "PreRefl File",
                "Internal, using xraylib " + ("**NOT AVAILABLE**" if not XRAYLIB_AVAILABLE else ""),
                "Internal, using DABAX",
            ],
            callback=self.set_ri_calculation_mode,
            sendSelectedValue=False,
            orientation="horizontal",
            tooltip="ri_calculation_mode",
        )

        self.calculation_mode_1 = oasysgui.widgetBox(box, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(
            self.calculation_mode_1,
            self,
            "refraction_index",
            "Refraction index",
            tooltip="refraction_index",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )
        oasysgui.lineEdit(
            self.calculation_mode_1,
            self,
            "attenuation_coefficient",
            "Attenuation coefficient [m-1]",
            tooltip="attenuation_coefficient",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )

        self.calculation_mode_2 = oasysgui.widgetBox(box, "", addSpace=False, orientation="vertical")
        prerefl_box = oasysgui.widgetBox(self.calculation_mode_2, "", addSpace=True, orientation="horizontal")
        self.le_file_prerefl = oasysgui.lineEdit(
            prerefl_box,
            self,
            "prerefl_file",
            "File PreRefl",
            tooltip="prerefl_file",
            labelWidth=100,
            valueType=str,
            orientation="horizontal",
        )
        gui.button(prerefl_box, self, "...", callback=self.select_file_prerefl)

        self.calculation_mode_3 = oasysgui.widgetBox(box, "", addSpace=False, orientation="vertical")
        oasysgui.lineEdit(
            self.calculation_mode_3,
            self,
            "material",
            "Material",
            tooltip="material",
            labelWidth=250,
            valueType=str,
            orientation="horizontal",
            callback=self.set_density,
        )
        oasysgui.lineEdit(
            self.calculation_mode_3,
            self,
            "density",
            "Density [g/cm3]",
            tooltip="density",
            labelWidth=250,
            valueType=float,
            orientation="horizontal",
        )

    def set_aperturing(self, is_init=False):
        self.box_aperturing_shape.setVisible(self.aperturing == 1)

    def set_ri_calculation_mode(self):
        self.calculation_mode_1.setVisible(self.ri_calculation_mode == 0)
        self.calculation_mode_2.setVisible(self.ri_calculation_mode == 1)
        self.calculation_mode_3.setVisible(self.ri_calculation_mode > 1)
        self.dabax_box.setVisible(self.ri_calculation_mode == 3)

    def select_surface_data_file(self):
        self.le_surface_data_file.setText(
            oasysgui.selectFileFromDialog(
                self,
                self.surface_data_file,
                "Select Thickness Map File",
                file_extension_filter="Data Files (*.h5 *.hdf5 *.hdf)",
            )
        )

    def view_surface_data_file(self):
        try:
            self._view_transformed_surface(ShowSurfaceErrorDataFileDialog)
        except Exception as exception:
            self.prompt_exception(exception)

    def view_image_data_file(self):
        try:
            self._view_transformed_surface(ShowImageErrorDataFileDialog)
        except Exception as exception:
            self.prompt_exception(exception)

    def select_file_prerefl(self):
        self.le_file_prerefl.setText(
            oasysgui.selectFileFromDialog(
                self,
                self.prerefl_file,
                "Select File PreRefl",
                file_extension_filter="Data Files (*.dat)",
            )
        )

    def set_density(self):
        if self.material is not None and self.material.strip() != "":
            self.material = self.material.strip()
            self.density = ShadowPhysics.getMaterialDensity(self.material)

    def get_coordinates_instance(self):
        return ElementCoordinates(
            p=self.source_plane_distance,
            q=self.image_plane_distance,
            angle_radial=0.0,
            angle_azimuthal=0.0,
            angle_radial_out=numpy.pi,
        )

    def get_optical_element_instance(self):
        self.check_data()

        if self.aperturing == 0:
            boundary_shape = None
        elif self.aperture_shape == 0:
            boundary_shape = Rectangle(
                x_left=self.slit_center_xaxis - 0.5 * self.slit_width_xaxis,
                x_right=self.slit_center_xaxis + 0.5 * self.slit_width_xaxis,
                y_bottom=self.slit_center_zaxis - 0.5 * self.slit_height_zaxis,
                y_top=self.slit_center_zaxis + 0.5 * self.slit_height_zaxis,
            )
        else:
            boundary_shape = Ellipse(
                a_axis_min=self.slit_center_xaxis - 0.5 * self.slit_width_xaxis,
                a_axis_max=self.slit_center_xaxis + 0.5 * self.slit_width_xaxis,
                b_axis_min=self.slit_center_zaxis - 0.5 * self.slit_height_zaxis,
                b_axis_max=self.slit_center_zaxis + 0.5 * self.slit_height_zaxis,
            )

        dabax = None
        if self.ri_calculation_mode == 3:
            dabax = DabaxXraylib(
                file_f1f2="%s" % dabax_f1f2_files()[self.DABAX_F1F2_FILE_INDEX],
                file_CrossSec="%s" % dabax_crosssec_files()[self.DABAX_CROSSSEC_FILE_INDEX],
            )

        try:
            name = self.getNode().title
        except Exception:
            name = "Phase Deflector"

        return S4NumericalMeshPhaseDeflector(
            name=name,
            boundary_shape=boundary_shape,
            surface_data_file=self.surface_data_file,
            material=self.material,
            density=self.density,
            f_r_ind=self.ri_calculation_mode,
            file_r_ind=self.prerefl_file,
            r_ind=self.refraction_index,
            r_attenuation=self.attenuation_coefficient,
            dabax=dabax,
            apply_to_lost=self.apply_to_lost == 1,
            shift_thickness_to_zero=self.shift_thickness_to_zero == 1,
            thickness_scaling=self.thickness_scaling,
            coordinate_scaling=self.coordinate_scaling,
            invert_surface=self.invert_surface == 1,
        )

    def get_beamline_element_instance(self):
        return S4NumericalMeshPhaseDeflectorElement()

    def check_data(self):
        if self.surface_data_file in (None, "", NO_FILE_SPECIFIED):
            raise ValueError("No thickness map file specified.")

        congruence.checkFile(self.surface_data_file)
        congruence.checkStrictlyPositiveNumber(
            self.coordinate_scaling, "Coordinate scaling"
        )

        if self.aperturing == 1:
            congruence.checkStrictlyPositiveNumber(self.slit_width_xaxis, "Aperture width")
            congruence.checkStrictlyPositiveNumber(self.slit_height_zaxis, "Aperture height")

        if self.ri_calculation_mode == 1:
            congruence.checkFile(self.prerefl_file)
        elif self.ri_calculation_mode > 1:
            congruence.checkEmptyString(self.material, "Material")
            congruence.checkStrictlyPositiveNumber(self.density, "Density")

    @Inputs.thickness_errors_data
    def set_thickness_errors_data(self, data):
        if data is not None:
            files = getattr(data, "thickness_error_profile_data_files", None)
            if files:
                self.surface_data_file = files[0]
                self.le_surface_data_file.setText(self.surface_data_file)
            else:
                QMessageBox.warning(self, "Warning", "No thickness files in input data", QMessageBox.Ok)

    def _view_transformed_surface(self, dialog_class):
        if self.surface_data_file in (None, "", NO_FILE_SPECIFIED):
            raise ValueError("No thickness map file specified.")
        optical_element = S4NumericalMeshPhaseDeflector(
            surface_data_file=self.surface_data_file,
            shift_thickness_to_zero=self.shift_thickness_to_zero == 1,
            thickness_scaling=self.thickness_scaling,
            coordinate_scaling=self.coordinate_scaling,
            invert_surface=self.invert_surface == 1,
        )
        data = optical_element.get_thickness_map(validate=False)
        temporary = tempfile.NamedTemporaryFile(suffix=".h5", delete=False)
        temporary.close()
        try:
            write_surface_file(
                data["profile"], data["x_axis"], data["y_axis"],
                temporary.name, overwrite=True,
            )
            dialog = dialog_class(parent=self, file_name=temporary.name)
        finally:
            if os.path.exists(temporary.name):
                os.remove(temporary.name)
        dialog.show()

    @Inputs.prerefl_preprocessor_data
    def set_PreReflPreProcessorData(self, data):
        if data is not None:
            if data.prerefl_data_file != PreReflPreProcessorData.NONE:
                self.prerefl_file = data.prerefl_data_file
                self.le_file_prerefl.setText(self.prerefl_file)
                self.ri_calculation_mode = 1
                self.set_ri_calculation_mode()
            else:
                QMessageBox.warning(self, "Warning", "Incompatible PreProcessor Data", QMessageBox.Ok)

    def _plot_results(self, output_beam, footprint, progressBarValue=80):
        if not self.view_type == 2:
            if ShadowCongruence.check_empty_beam(output_beam):
                self.view_type_combo.setEnabled(False)

                ShadowPlot.set_conversion_active(self._is_conversion_active())

                variables = self._get_variables_to_plot()
                titles = self._get_titles()
                xtitles = self._get_x_titles()
                ytitles = self._get_y_titles()
                xums = self._get_x_um()
                yums = self._get_y_um()

                try:
                    if self.view_type == 1:
                        self._plot_xy_preview(output_beam, progressBarValue + 4, variables[0][0], variables[0][1], plot_canvas_index=0, title=titles[0], xtitle=xtitles[0], ytitle=ytitles[0])
                        self._plot_xy_preview(output_beam, progressBarValue + 8, variables[1][0], variables[1][1], plot_canvas_index=1, title=titles[1], xtitle=xtitles[1], ytitle=ytitles[1])
                        self._plot_xy_preview(output_beam, progressBarValue + 12, variables[2][0], variables[2][1], plot_canvas_index=2, title=titles[2], xtitle=xtitles[2], ytitle=ytitles[2])
                        self._plot_xy_preview(output_beam, progressBarValue + 16, variables[3][0], variables[3][1], plot_canvas_index=3, title=titles[3], xtitle=xtitles[3], ytitle=ytitles[3])
                        self._plot_histo_preview(output_beam, progressBarValue + 20, variables[4], plot_canvas_index=4, title=titles[4], xtitle=xtitles[4], ytitle=ytitles[4])
                        self._plot_xy_preview(footprint, progressBarValue + 20, 1, 3, plot_canvas_index=5, title="Footprint", xtitle="X [m]", ytitle="Z [m]", is_footprint=True)
                    elif self.view_type == 0:
                        self._plot_xy_detailed(output_beam, progressBarValue + 4, variables[0][0], variables[0][1], plot_canvas_index=0, title=titles[0], xtitle=xtitles[0], ytitle=ytitles[0], xum=xums[0], yum=yums[0])
                        self._plot_xy_detailed(output_beam, progressBarValue + 8, variables[1][0], variables[1][1], plot_canvas_index=1, title=titles[1], xtitle=xtitles[1], ytitle=ytitles[1], xum=xums[1], yum=yums[1])
                        self._plot_xy_detailed(output_beam, progressBarValue + 12, variables[2][0], variables[2][1], plot_canvas_index=2, title=titles[2], xtitle=xtitles[2], ytitle=ytitles[2], xum=xums[2], yum=yums[2])
                        self._plot_xy_detailed(output_beam, progressBarValue + 16, variables[3][0], variables[3][1], plot_canvas_index=3, title=titles[3], xtitle=xtitles[3], ytitle=ytitles[3], xum=xums[3], yum=yums[3])
                        self._plot_histo_detailed(output_beam, progressBarValue + 20, variables[4], plot_canvas_index=4, title=titles[4], xtitle=xtitles[4], ytitle=ytitles[4], xum=xums[4])
                        self._plot_xy_detailed(footprint, progressBarValue + 20, 1, 3, plot_canvas_index=5, title="Footprint", xtitle="X [m]", ytitle="Z [m]", xum="X [m]", yum="Z [m]", is_footprint=True)
                except Exception as exception:
                    self.view_type_combo.setEnabled(True)
                    raise Exception("Data not plottable: No good rays or bad content\nexception: " + str(exception))

                self.view_type_combo.setEnabled(True)
            else:
                raise Exception("Empty Beam")

        self.plotted_beam = output_beam
        self.footprint_beam = footprint


add_widget_parameters_to_module(__name__)


if __name__ == "__main__":
    from shadow4.beamline.s4_beamline import S4Beamline
    import sys
    from orangecontrib.shadow4.util.shadow4_objects import ShadowData, PreReflPreProcessorData, VlsPgmPreProcessorData

    def get_test_beam():
        from shadow4.beamline.s4_beamline import S4Beamline

        beamline = S4Beamline()
        #
        #
        #
        from shadow4.sources.source_geometrical.source_geometrical import SourceGeometrical
        light_source = SourceGeometrical(name='Geometrical Source', nrays=5000, seed=5676561)
        light_source.set_spatial_type_point()
        light_source.set_depth_distribution_off()
        light_source.set_angular_distribution_gaussian(sigdix=1e-05, sigdiz=1e-05)
        light_source.set_energy_distribution_uniform(value_min=9950, value_max=10050, unit='eV')
        light_source.set_polarization(polarization_degree=1, phase_diff=0, coherent_beam=0)
        beam = light_source.get_beam()

        beamline.set_light_source(light_source)

        return ShadowData(beam=beam, beamline=S4Beamline(light_source=light_source))

    from AnyQt.QtWidgets import QApplication
    a = QApplication(sys.argv)
    ow = OWPhaseDeflector()
    ow.set_shadow_data(get_test_beam())

    ow.source_plane_distance = 10.0
    ow.image_plane_distance = 0.0
    ow.ri_calculation_mode = 3
    ow.material = "Be"
    ow.density = 1.85
    ow.surface_data_file = '/home/srio/Oasys2/lens_interface_1.h5'

    ow.show()
    a.exec()
    ow.saveSettings()
