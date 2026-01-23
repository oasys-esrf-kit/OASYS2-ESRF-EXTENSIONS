from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

from shadow4.beamline.optical_elements.ideal_elements.s4_empty import S4Empty, S4EmptyElement
from shadow4.beamline.optical_elements.crystals.s4_plane_crystal import S4PlaneCrystal

from orangewidget.settings import Setting
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input
from oasys2.widget import gui as oasysgui
from orangecontrib.shadow4.widgets.gui.ow_optical_element import OWOpticalElement

import numpy
from shadow4.optical_surfaces.s4_conic import S4Conic
from shadow4.beamline.optical_elements.compound.s4_compound import S4Compound, S4CompoundElement
from shadow4.beamline.optical_elements.mirrors.s4_conic_mirror import S4ConicMirror, S4ConicMirrorElement
from shadow4.beamline.optical_elements.crystals.s4_conic_crystal import S4ConicCrystal

class OWChannelCut(OWOpticalElement):
    name        = "ChannelCut"
    description = "Shadow Compound Element: ChannelCut"
    icon        = "icons/channelcut.png"

    priority = 11.0

    reflector_or_crystal = Setting(0)
    crystal_separation = Setting(0.005)
    pitch = Setting(0.0)
    roll = Setting(0.0)
    yaw = Setting(0.0)

    def __init__(self):
        super().__init__(has_footprint=False)

    def create_basic_settings_subtabs(self, tabs_basic_settings):
        return oasysgui.createTabPage(tabs_basic_settings, "Channel Cut")  # to be populated

    def populate_basic_setting_subtabs(self, tab_1):
        gui.comboBox(tab_1, self, "reflector_or_crystal", tooltip="reflector_or_crystal",
                     label="Plane-surface reflecivity", labelWidth=120,
                     items=["ideal reflector",
                            "Si111 crystal"],
                     sendSelectedValue=False, orientation="horizontal",
                     )
        oasysgui.lineEdit(tab_1, self, "crystal_separation", "Crystal separation [m]",
                          tooltip="crystal_separation",
                          labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(tab_1, self, "pitch", "Misalign pitch [rad]", tooltip="pitch",
                          labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(tab_1, self, "roll", "Misalign roll [rad]", tooltip="roll",
                          labelWidth=260, valueType=float, orientation="horizontal")
        oasysgui.lineEdit(tab_1, self, "yaw", "Misalign yaw [rad]", tooltip="yaw",
                          labelWidth=260, valueType=float, orientation="horizontal")
        gui.separator(self.tab_basic_settings)


    def get_optical_element_instance(self):
        try:
            name = self.getNode().title
        except:
            name = "Channel Cut Crystal Monochromator"

        boundary_shape = None

        ccc1 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, -1.0, -0.5 * self.crystal_separation]
        ccc2 = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, -0.5 * self.crystal_separation]

        # Rx, beta
        R_pitch = [[1, 0, 0],
                   [0, numpy.cos(self.pitch), -numpy.sin(self.pitch)],
                   [0, numpy.sin(self.pitch), numpy.cos(self.pitch)]]
        # Ry, gamma
        R_roll = [[numpy.cos(self.roll), 0, numpy.sin(self.roll)],
                  [0, 1, 0],
                  [-numpy.sin(self.roll), 0, numpy.cos(self.roll)]]
        # Rz, alpha
        R_yaw = [[numpy.cos(self.yaw), -numpy.sin(self.yaw), 0],
                 [numpy.sin(self.yaw), numpy.cos(self.yaw), 0],
                 [0, 0, 1]]
        # R = Rz Rx Ry
        R = numpy.array(R_yaw) @ numpy.array(R_pitch) @ numpy.array(R_roll)

        ccc1 = S4Conic.rotate_and_translate_coefficients(ccc1, R, [0,0,0])
        ccc2 = S4Conic.rotate_and_translate_coefficients(ccc2, R, [0,0,0])

        if self.reflector_or_crystal == 0:
            optical_element1 = S4ConicMirror(name='Mirror 1', boundary_shape=boundary_shape,
                                             conic_coefficients=ccc1,
                                             f_reflec=0, f_refl=6, file_refl='<none>',
                                             refraction_index=0.99999 + 0.001j,
                                             coating_material='Ni', coating_density=8.902, coating_roughness=0)

            optical_element2 = S4ConicMirror(name='Mirror 2', boundary_shape=boundary_shape,
                                             conic_coefficients=ccc2,
                                             f_reflec=0, f_refl=6, file_refl='<none>',
                                             refraction_index=0.99999 + 0.001j,
                                             coating_material='Ni', coating_density=8.902, coating_roughness=0)
        else:
            optical_element1 = S4ConicCrystal(name='Crystal 1',
                                              boundary_shape=boundary_shape,
                                              conic_coefficients=ccc1,
                                              material='Si', miller_index_h=1, miller_index_k=1, miller_index_l=1,
                                              f_bragg_a=False, asymmetry_angle=0.0,
                                              is_thick=1, thickness=0.001,
                                              f_central=0, f_phot_cent=0, phot_cent=5000.0,
                                              file_refl='bragg.dat',
                                              f_ext=0,
                                              material_constants_library_flag=1,
                                              # 0=xraylib,1=dabax,2=preprocessor v1,3=preprocessor v2
                                              )

            optical_element2 = S4ConicCrystal(name='Crystal 2',
                                              boundary_shape=boundary_shape,
                                              conic_coefficients=ccc2,
                                              material='Si', miller_index_h=1, miller_index_k=1, miller_index_l=1,
                                              f_bragg_a=False, asymmetry_angle=0.0,
                                              is_thick=1, thickness=0.001,
                                              f_central=0, f_phot_cent=0, phot_cent=5000.0,
                                              file_refl='bragg.dat',
                                              f_ext=0,
                                              material_constants_library_flag=1,
                                              # 0=xraylib,1=dabax,2=preprocessor v1,3=preprocessor v2
                                              )

        return S4Compound(name=name, oe_list=[optical_element1, optical_element2])



    def get_beamline_element_instance(self):
        return S4CompoundElement()

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    import sys
    from shadow4.beamline.s4_beamline import S4Beamline
    from shadow4.sources.source_geometrical.source_geometrical import SourceGeometrical
    from orangecontrib.shadow4.util.shadow4_objects import ShadowData
    def get_test_beam():
        from shadow4.sources.source_geometrical.source_geometrical import SourceGeometrical
        light_source = SourceGeometrical(name='SourceGeometrical', nrays=5000, seed=5676561)
        light_source.set_spatial_type_point()
        light_source.set_angular_distribution_flat(hdiv1=-0.000000, hdiv2=0.000000, vdiv1=-0.000000, vdiv2=0.000000)
        light_source.set_energy_distribution_uniform(value_min=7990.000000, value_max=8010.000000, unit='eV')
        light_source.set_polarization(polarization_degree=1.000000, phase_diff=0.000000, coherent_beam=0)
        beam = light_source.get_beam()
        return ShadowData(beam=beam, beamline=S4Beamline(light_source=light_source))

    from AnyQt.QtWidgets import QApplication
    a = QApplication(sys.argv)
    ow = OWChannelCut()
    # ow.set_shadow_data(get_test_beam())
    ow.show()
    a.exec()
    ow.saveSettings()
