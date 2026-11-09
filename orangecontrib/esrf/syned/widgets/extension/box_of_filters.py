import numpy
import sys
import json
import urllib.request

from AnyQt.QtWidgets import QMessageBox

from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Output

from oasys2.widget import gui as oasysgui
from oasys2.widget.util import congruence

# keep OWOpticalElement import from syned widget package (usually compatible)
from orangecontrib.syned.widgets.gui.ow_optical_element import OWOpticalElement

from syned.beamline.optical_elements.absorbers.filter_box import FilterBox
from syned.beamline.beamline import Beamline
from syned.beamline.element_coordinates import ElementCoordinates
from syned.beamline.beamline_element import BeamlineElement

from syned.util.json_tools import load_from_json_file, load_from_json_url, load_from_json_text

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module

class OWBoxOfFilters(OWOpticalElement):

    name = "Box of Filters"
    description = "Syned: Box of Filters"
    icon = "icons/box_of_filters.png"
    priority = 3.1

    att1  = Setting(0)
    att2  = Setting(0)
    att3  = Setting(0)
    att4  = Setting(0)
    att5  = Setting(0)
    att6  = Setting(0)
    att7  = Setting(0)
    att8  = Setting(0)
    att9  = Setting(0)
    att10 = Setting(0)

    n_blocks = Setting(3)
    syned_file_name = Setting("https://raw.githubusercontent.com/oasys-esrf-kit/OASYS1-ESRF-Extensions/master/orangecontrib/esrf/xoppy/data/bm05_wb_attenuators.json")
    # syned_file_name = Setting("/home/srio/OASYS2.0/modelling_team_scripts_and_workspaces/id11/WATTDOG/SPECTRA/id11_wattdog_attenuators_2028_syned_no_density.json")

    syned_send_selection = Setting(0)

    # serialized copy of the loaded FilterBox, persisted in the .ows workspace
    # (combo items and self.syned_filterbox are otherwise rebuilt only on file read)
    syned_filterbox_json = Setting("")

    def __init__(self):
        self.syned_filterbox = FilterBox()

        super().__init__(allow_angle_radial=False, allow_angle_azimuthal=False)

        # restore the FilterBox saved in the workspace (.ows), if any, without
        # overwriting the restored att1..att10 selections
        if self.syned_filterbox_json:
            try:
                self.syned_filterbox = load_from_json_text(self.syned_filterbox_json)
                self.restore_blocks_from_filterbox()
            except Exception:
                pass

    def draw_specific_box(self):

        #################
        box_json = oasysgui.widgetBox(self.tab_bas, "json files i/o", addSpace=True, orientation="vertical")

        file_box = oasysgui.widgetBox(box_json, "", addSpace=False, orientation="horizontal")

        self.le_syned_file_name = oasysgui.lineEdit(file_box, self, "syned_file_name", "File Name/URL",
                                                    labelWidth=150, valueType=str, orientation="horizontal")

        gui.button(file_box, self, "...", callback=self.select_syned_file, width=25)

        button_box = oasysgui.widgetBox(box_json, "", addSpace=False, orientation="horizontal")

        button = gui.button(button_box, self, "Read Syned File", callback=self.read_syned_file)
        button.setFixedHeight(25)

        button = gui.button(button_box, self, "Read plane json File", callback=self.read_plane_json_file)
        button.setFixedHeight(25)

        button = gui.button(button_box, self, "Write Syned File...", callback=self.write_syned_file)
        button.setFixedHeight(25)

        #################
        box_send = oasysgui.widgetBox(self.tab_bas, "send object", addSpace=True, orientation="vertical")

        gui.comboBox(box_send, self, "syned_send_selection",
                     label="Send syned object with:",
                     items=['All filters','Selected filters'],
                     orientation="horizontal", labelWidth=250, editable=0)


        ################
        filter_box = oasysgui.widgetBox(self.tab_bas, "Box of Filters Setting", addSpace=True, orientation="vertical")

        box1 = gui.widgetBox(filter_box)
        gui.comboBox(box1, self, "n_blocks",
                     label="Number of blocks or axes",
                     items=['0','1','2','3','4','5','6','7','8','9','10'], callback=self.set_n_blocks,
                     orientation="horizontal", labelWidth=250, editable=0)

        # Att1..Att10: self.wid_attN (container) and self.wid_attN_combo.
        # Not editable: the combo value is an index into the block's filter list.
        for i in range(1, 11):
            box = gui.widgetBox(box1)
            combo = gui.comboBox(box, self, "att%d" % i,
                                 label="Att%d" % i,
                                 items=['Undefined'],
                                 orientation="horizontal", labelWidth=150, editable=0)
            setattr(self, "wid_att%d" % i, box)
            setattr(self, "wid_att%d_combo" % i, combo)

        self.set_visibility()

    def set_n_blocks(self):
        self.set_visibility()

    def set_visibility(self):
        for i in range(1, 11):
            getattr(self, "wid_att%d" % i).setVisible(self.n_blocks >= i)

    def select_syned_file(self):
        self.le_syned_file_name.setText(oasysgui.selectFileFromDialog(self, self.syned_file_name, "Open json File"))

    def read_syned_file(self):
        try:
            congruence.checkEmptyString(self.syned_file_name, "Syned File Name/Url")

            if (len(self.syned_file_name) > 7 and self.syned_file_name[:7] == "http://") or \
               (len(self.syned_file_name) > 8 and self.syned_file_name[:8] == "https://"):
                congruence.checkUrl(self.syned_file_name)
                is_remote = True
            else:
                congruence.checkFile(self.syned_file_name)
                is_remote = False

            try:
                if is_remote:
                    content = load_from_json_url(self.syned_file_name)
                else:
                    content = load_from_json_file(self.syned_file_name)

                if isinstance(content, FilterBox):
                    self.configure_blocks_from_syned_json(content)
                    self.syned_filterbox = content
                    self.syned_filterbox_json = content.to_json()  # persist in workspace
                else:
                    raise Exception("json file must contain a SYNED FilterBox")
            except Exception as e:
                raise Exception("Error reading SYNED FilterBox from file: " + str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e), QMessageBox.StandardButton.Ok)

    def read_plane_json_file(self):
        try:
            congruence.checkEmptyString(self.syned_file_name, "plane json File Name/Url")

            if (len(self.syned_file_name) > 7 and self.syned_file_name[:7] == "http://") or \
               (len(self.syned_file_name) > 8 and self.syned_file_name[:8] == "https://"):
                congruence.checkUrl(self.syned_file_name)
                is_remote = True
            else:
                congruence.checkFile(self.syned_file_name)
                is_remote = False

            try:
                if is_remote:
                    response = urllib.request.urlopen(self.syned_file_name)
                    att_dic = json.load(response)
                else:
                    with open(self.syned_file_name) as att_file:
                        att_dic = json.load(att_file)

                if isinstance(att_dic, dict):
                    fb_syned = FilterBox.from_plane_json_dict(att_dic)
                    self.configure_blocks_from_syned_json(fb_syned)
                    self.syned_filterbox = fb_syned
                    self.syned_filterbox_json = fb_syned.to_json()  # persist in workspace
                else:
                    raise Exception("json file must contain a FilterBox")
            except Exception as e:
                raise Exception("Error reading filter box from plane json file: " + str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e), QMessageBox.StandardButton.Ok)

    def write_syned_file(self):
        try:
            filename = oasysgui.selectSaveFileFromDialog(self, message="Save File", default_file_name="", file_extension_filter="*.*")
            if filename is not None:
                self.syned_filterbox.to_json(filename)
                QMessageBox.information(self, "File Save", "JSON file %s correctly written to disk" % filename, QMessageBox.StandardButton.Ok)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e), QMessageBox.StandardButton.Ok)

    def update_combo(self, combo, new_input):
        # replace ALL items: entries left over from a larger, previously loaded box
        # would point to filters that do not exist in the current one
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems([str(item) for item in new_input])
        finally:
            combo.blockSignals(False)

    def configure_blocks_from_syned_json(self, content):
        if content.get_n() > 10:
            raise Exception('Maximum of 10 blocks allowed.')
        else:
            self.n_blocks = content.get_n()

        self.set_visibility()

        # update combo boxes
        combos = [self.wid_att1_combo, self.wid_att2_combo, self.wid_att3_combo,
                  self.wid_att4_combo, self.wid_att5_combo, self.wid_att6_combo,
                  self.wid_att7_combo, self.wid_att8_combo, self.wid_att9_combo,
                  self.wid_att10_combo]
        atts = ["att1", "att2", "att3", "att4", "att5",
                "att6", "att7", "att8", "att9", "att10"]
        for i in range(content.get_n()):
            blc = content.get_item(i)
            items = [blc.get_item(j).get_name() for j in range(blc.get_n())]
            self.update_combo(combos[i], items)
            # activate the selection stored in the block (e.g. "_att_pos")
            selection = blc.get_selection()
            if selection is None:        selection = 0  # syned FilterBlock default: no selection
            elif selection < 0:          selection = 0
            elif selection >= len(items): selection = max(0, len(items) - 1)
            setattr(self, atts[i], selection)   # updates the bound setting (read by get_optical_element)
            combos[i].setCurrentIndex(selection)  # ensure the combo display matches

    def restore_blocks_from_filterbox(self):
        # repopulate combos from self.syned_filterbox on workspace restore, KEEPING
        # the restored att1..att10 selections (unlike configure_blocks_from_syned_json,
        # which resets them to each block's stored selection / "_att_pos")
        content = self.syned_filterbox
        if content is None or content.get_n() == 0: return

        self.set_visibility()  # honour the restored n_blocks

        combos = [self.wid_att1_combo, self.wid_att2_combo, self.wid_att3_combo,
                  self.wid_att4_combo, self.wid_att5_combo, self.wid_att6_combo,
                  self.wid_att7_combo, self.wid_att8_combo, self.wid_att9_combo,
                  self.wid_att10_combo]
        atts = ["att1", "att2", "att3", "att4", "att5",
                "att6", "att7", "att8", "att9", "att10"]
        for i in range(min(content.get_n(), 10)):
            blc = content.get_item(i)
            items = [blc.get_item(j).get_name() for j in range(blc.get_n())]
            self.update_combo(combos[i], items)
            sel = getattr(self, atts[i])  # the value restored from the .ows
            if sel < 0:             sel = 0
            elif sel >= len(items): sel = max(0, len(items) - 1)
            setattr(self, atts[i], sel)
            combos[i].setCurrentIndex(sel)

    def get_optical_element(self):
        n_available = self.syned_filterbox.get_n()
        if n_available == 0:
            raise Exception("No filter box loaded: read a Syned or plane json file first.")
        if self.n_blocks > n_available:
            raise Exception("The loaded filter box has %d block(s), but %d are requested.\n"
                            "Reduce the number of blocks or read another file." % (n_available, self.n_blocks))

        filterbox = self.syned_filterbox.duplicate()
        filterbox.set_n(self.n_blocks)
        ss = [self.att1, self.att2, self.att3, self.att4, self.att5,
              self.att6, self.att7, self.att8, self.att9, self.att10]
        for i in range(self.n_blocks):
            block = filterbox.get_item(i)
            if not 0 <= ss[i] < block.get_n():
                raise Exception("Att%d: selection %d out of range (block has %d filters)." % (i + 1, ss[i], block.get_n()))
            block.set_selection(ss[i])
        return filterbox

    def send_data(self): # overwrite this method to allow sending syned object with selection only
        try:
            self.check_data()

            if self.beamline is None: self.beamline = Beamline()


            if self.syned_send_selection:
                optical_element = self.get_optical_element().duplicate_using_selected_only()
            else:
                optical_element = self.get_optical_element()

            beamline_element = BeamlineElement(optical_element=optical_element,
                                               coordinates=ElementCoordinates(p=self.p,
                                                                              q=self.q,
                                                                              angle_radial=numpy.radians(self.angle_radial),
                                                                              angle_azimuthal=numpy.radians(self.angle_azimuthal)))

            output_beamline = self.beamline.duplicate()
            output_beamline.append_beamline_element(beamline_element=beamline_element)

            self.Outputs.syned_data.send(output_beamline)

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e), QMessageBox.Ok)

            self.setStatusMessage("")
            self.progressBarFinished()

            if self.IS_DEVELOP: raise e

add_widget_parameters_to_module(__name__)

if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication
    app = QApplication(sys.argv)
    w = OWBoxOfFilters()
    w.show()
    app.exec()
