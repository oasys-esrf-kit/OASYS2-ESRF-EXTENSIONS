from copy import deepcopy
import contextlib
import io
import os
import pathlib
import sys
import time
import uuid

import joblib
from orangewidget import gui
from orangewidget.settings import Setting
from orangewidget.widget import Input, Output

from oasys2.canvas.util.canvas_util import add_widget_parameters_to_module
from oasys2.widget import gui as oasysgui
from oasys2.widget.gui import MessageDialog, Styles
from oasys2.widget.widget import OWAction, OWWidget
from shadow4.tools.parallel import (
    cpu_info_text,
    get_parallel_runner_prototype,
    load_runner_module,
)
from orangecontrib.shadow4.util.python_script import PythonScript
from orangecontrib.shadow4.util.shadow4_objects import ShadowData


class OWParallel(OWWidget):
    name = "Parallel"
    description = "Run additional Shadow4 beamline repetitions in parallel"
    icon = "icons/uicons_parallel.png"
    priority = 6
    keywords = ["esrf", "shadow4", "parallel", "joblib", "repetitions", "seed"]

    want_main_area = 1

    class Inputs:
        shadow_data = Input("Shadow Data", ShadowData, default=True, auto_summary=False)

    class Outputs:
        shadow_data = Output("Shadow Data", ShadowData, default=True, auto_summary=False)

    number_of_repetitions = Setting(5)
    number_of_rays = Setting(10000)
    n_jobs = Setting(-1)
    base_seed = Setting(0)

    def __init__(self):
        super().__init__()

        self._shadow_data = None

        self.runaction = OWAction("Run Parallel", self)
        self.runaction.triggered.connect(self.run_parallel)
        self.addAction(self.runaction)

        button_box = oasysgui.widgetBox(
            self.controlArea,
            "",
            addSpace=False,
            orientation="horizontal",
            width=390,
        )
        button = gui.button(button_box, self, "Run Parallel", callback=self.run_parallel)
        button.setStyleSheet(Styles.button_blue)

        settings_box = oasysgui.widgetBox(
            self.controlArea,
            "Parallel Run",
            addSpace=True,
            orientation="vertical",
            width=390,
        )
        oasysgui.lineEdit(
            settings_box,
            self,
            "number_of_repetitions",
            "Number of repetitions",
            labelWidth=190,
            valueType=int,
            orientation="horizontal",
            callback=self.set_script,
        )
        self.le_number_of_rays = oasysgui.lineEdit(
            settings_box,
            self,
            "number_of_rays",
            "Number of rays",
            labelWidth=190,
            valueType=int,
            orientation="horizontal",
            callback=self.set_script,
        )
        oasysgui.lineEdit(
            settings_box,
            self,
            "n_jobs",
            "Number of cores",
            labelWidth=190,
            valueType=int,
            orientation="horizontal",
            callback=self.set_script,
        )
        self.le_base_seed = oasysgui.lineEdit(
            settings_box,
            self,
            "base_seed",
            "Base seed",
            labelWidth=190,
            valueType=int,
            orientation="horizontal",
            callback=self.set_script,
        )

        # info_box = oasysgui.widgetBox(
        #     self.controlArea,
        #     "Input",
        #     addSpace=True,
        #     orientation="vertical",
        #     width=390,
        # )
        # gui.label(info_box, self, "All repetitions are recalculated from the input beamline.")
        # gui.label(info_box, self, "Number of rays is pre-filled from the input light source.")

        self.main_tabs = oasysgui.tabWidget(self.mainArea)
        out_tab = oasysgui.createTabPage(self.main_tabs, "Output")
        script_tab = oasysgui.createTabPage(self.main_tabs, "Script")

        self.run_output = oasysgui.textArea(height=560, width=760)
        output_box = gui.widgetBox(
            out_tab,
            "Parallel run log",
            addSpace=True,
            orientation="horizontal",
        )
        output_box.layout().addWidget(self.run_output)

        self.shadow4_script = PythonScript()
        self.shadow4_script.code_area.setFixedHeight(400)
        self.shadow4_script.console.locals["__name__"] = "__main__"

        script_box = gui.widgetBox(
            script_tab,
            "Python script",
            addSpace=True,
            orientation="horizontal",
        )
        script_box.layout().addWidget(self.shadow4_script)
        self.set_script()

        gui.rubber(self.controlArea)

    @Inputs.shadow_data
    def set_shadow_data(self, shadow_data):
        self._shadow_data = shadow_data
        self._prefill_number_of_rays()
        self._prefill_base_seed()
        self.set_script()

    def set_script(self):
        if not hasattr(self, "shadow4_script"):
            return

        if self._shadow_data is None or self._shadow_data.beamline is None:
            self.shadow4_script.set_code("# No Shadow Data input received.")
            return

        try:
            self.shadow4_script.set_code(self._script_code())
        except Exception as exception:
            self.shadow4_script.set_code(
                "Problem in writing python script:\n%s" % str(exception)
            )

    def run_parallel(self):
        self.setStatusMessage("")
        self.Outputs.shadow_data.send(None)
        self.run_output.setText("")

        stream = io.StringIO()
        progress_started = False

        try:
            self._validate_input()
            number_of_repetitions = self._validate_number_of_repetitions()
            number_of_rays = self._validate_number_of_rays()
            n_jobs = self._validate_n_jobs()

            self.progressBarInit()
            progress_started = True

            with contextlib.redirect_stdout(stream):
                output_data = self._run(number_of_repetitions, number_of_rays, n_jobs)

            log = stream.getvalue().strip()
            self.run_output.setText(log)
            print(log)

            self.Outputs.shadow_data.send(output_data)
            self.setStatusMessage("Accumulated Shadow Data emitted.")
        except Exception as exception:
            self.run_output.setText(str(exception))
            self.setStatusMessage(str(exception))
            MessageDialog.message(
                parent=self,
                title="Parallel Run Error",
                type="critical",
                message=str(exception),
            )
        finally:
            if progress_started:
                self.progressBarFinished()

    def _run(self, number_of_repetitions, number_of_rays, n_jobs):
        t_total = time.perf_counter()

        self.progressBarSet(10)
        runner_path = self._temporary_runner_script_path()
        try:
            runner_path.write_text(self._script_code(), encoding="utf-8")
            self._prepare_runner_import_path(runner_path)
            runner_module = load_runner_module(runner_path)

            t_parallel = time.perf_counter()
            seed_list, beamline_acc, beam_acc, footprint_acc = runner_module.run_parallel(
                number_of_repetitions=number_of_repetitions,
                number_of_rays=number_of_rays,
                n_jobs=n_jobs,
                base_seed=int(self.base_seed),
            )
            parallel_elapsed = time.perf_counter() - t_parallel
            self.progressBarSet(95)
        finally:
            try:
                runner_path.unlink()
            except Exception:
                pass

        output_data = ShadowData(
            beam=beam_acc,
            footprint=footprint_acc,
            number_of_rays=beam_acc.N,
            beamline=beamline_acc,
        )
        output_data.initial_flux = self._shadow_data.initial_flux
        output_data.scanning_data = self._shadow_data.scanning_data

        print("")
        print("Generated runner elapsed: %.3f s" % parallel_elapsed)
        print("Total elapsed: %.3f s" % (time.perf_counter() - t_total))
        print("Accumulated rays:", beam_acc.N)
        print("Seeds:", seed_list)

        self.progressBarSet(100)
        return output_data

    def _validate_input(self):
        if self._shadow_data is None:
            raise ValueError("No Shadow Data input received.")
        if self._shadow_data.beam is None:
            raise ValueError("Shadow Data does not contain a beam.")
        if self._shadow_data.beamline is None:
            raise ValueError("Shadow Data does not contain an S4 beamline.")
        if self._shadow_data.beamline.get_light_source() is None:
            raise ValueError("Shadow Data beamline does not contain a light source.")
        get_parallel_runner_prototype(self._shadow_data.beamline)

    def _validate_number_of_repetitions(self):
        number_of_repetitions = int(self.number_of_repetitions)

        if number_of_repetitions < 1:
            raise ValueError("Number of repetitions must be at least 1.")

        self.number_of_repetitions = number_of_repetitions
        return number_of_repetitions

    def _validate_number_of_rays(self):
        number_of_rays = int(self.number_of_rays)

        if number_of_rays < 1:
            raise ValueError("Number of rays must be at least 1.")

        self.number_of_rays = number_of_rays
        return number_of_rays

    def _validate_n_jobs(self):
        n_jobs = int(self.n_jobs)
        cpu_count = joblib.cpu_count()

        if n_jobs == 0:
            self.n_jobs = -1
            MessageDialog.message(
                parent=self,
                title="Invalid Core Count",
                type="warning",
                message="Number of cores cannot be 0. Using -1 instead.",
            )
            return -1

        if n_jobs > cpu_count:
            self.n_jobs = -1
            MessageDialog.message(
                parent=self,
                title="Invalid Core Count",
                type="warning",
                message=(
                    "Requested %d cores, but joblib reports %d available. "
                    "Using -1 instead.\n\n%s"
                )
                % (n_jobs, cpu_count, cpu_info_text()),
            )
            return -1

        self.n_jobs = n_jobs
        return n_jobs

    def _script_code(self):
        return deepcopy(self._shadow_data.beamline).to_python_code_parallel(
            number_of_repetitions=int(self.number_of_repetitions),
            number_of_rays=int(self.number_of_rays),
            n_jobs=int(self.n_jobs),
            base_seed=int(self.base_seed),
            output_file="s4_beam.h5",
        )

    def _temporary_runner_script_path(self):
        runner_dir = pathlib.Path(os.getcwd()) / ".oasys_shadow4_parallel"
        runner_dir.mkdir(parents=True, exist_ok=True)
        file_name = "parallel_runner_from_oasys_%d_%s.py" % (
            os.getpid(),
            uuid.uuid4().hex,
        )
        return runner_dir / file_name

    @staticmethod
    def _prepare_runner_import_path(runner_path):
        module_dir = str(pathlib.Path(runner_path).resolve().parent)

        if module_dir not in sys.path:
            sys.path.insert(0, module_dir)

        pythonpath = os.environ.get("PYTHONPATH", "")
        paths = [path for path in pythonpath.split(os.pathsep) if path]
        if module_dir not in paths:
            os.environ["PYTHONPATH"] = os.pathsep.join([module_dir] + paths)

    def _prefill_number_of_rays(self):
        if self._shadow_data is None:
            return

        try:
            light_source = self._prototype_light_source()
            if hasattr(light_source, "get_nrays"):
                number_of_rays = int(light_source.get_nrays())
            else:
                number_of_rays = int(self._shadow_data.beam.N)

            if number_of_rays > 0:
                self.number_of_rays = number_of_rays
                self.le_number_of_rays.setText(str(number_of_rays))
        except Exception:
            return

    def _prefill_base_seed(self):
        if self._shadow_data is None:
            return

        try:
            light_source = self._prototype_light_source()
            base_seed = int(light_source.get_seed())
            self.base_seed = base_seed
            self.le_base_seed.setText(str(base_seed))
        except Exception:
            return

    def _prototype_light_source(self):
        return get_parallel_runner_prototype(self._shadow_data.beamline).get_light_source()


add_widget_parameters_to_module(__name__)
