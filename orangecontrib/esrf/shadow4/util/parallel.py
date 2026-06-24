from copy import deepcopy
import importlib
import multiprocessing
import os
import pathlib
import re
import sys
import tempfile
import textwrap

import joblib
from shadow4.beamline.s4_beamline import S4Beamline
from shadow4.sources.s4_light_source_from_beamlines import S4LightSourceFromBeamlines
from shadow4.sources.source_geometrical.source_grid_cartesian import SourceGridCartesian
from shadow4.sources.source_geometrical.source_grid_polar import SourceGridPolar


UNSUPPORTED_PARALLEL_SOURCE_MESSAGE = (
    "SourceGridCartesian and SourceGridPolar are deterministic grid sources "
    "and do not support parallel repetitions in this widget. They do not expose "
    "a usable Monte Carlo seed, so parallel calculation cannot generate "
    "independent runs."
)


def cpu_info_text():
    lines = [
        "CPU availability:",
        "    os.cpu_count(): %s" % os.cpu_count(),
        "    multiprocessing.cpu_count(): %s" % multiprocessing.cpu_count(),
        "    joblib.cpu_count(): %s" % joblib.cpu_count(),
    ]

    try:
        lines.append("\n    CPU affinity: %s" % len(os.sched_getaffinity(0)))
    except AttributeError:
        lines.append("    CPU affinity: not available on this OS")

    return "\n".join(lines)


def print_cpu_info():
    text = cpu_info_text()
    print(text)
    return text


def runner_module_path():
    file_name = globals().get("__file__")
    if file_name is None:
        return "<interactive OASYS script>"
    return os.path.abspath(file_name)


def seed_for_iteration(base_seed, iteration):
    if base_seed == 0:
        return 0
    return int(base_seed + iteration * 2)


def concatenate_shadow_data(beamline, beam_list, footprint_list, seed_list, verbose=True):

    light_source_acc = S4LightSourceFromBeamlines(name='Accumulate Parallel Run')

    ntimes = len(seed_list)
    for i in range(ntimes):

        beam_list[i].clean_lost_rays()
        footprint_list[i].clean_lost_rays()
        
        if i == 0:
            beam_acc = beam_list[i].duplicate()
            footprint_acc = footprint_list[i].duplicate()
        else:
            beam_acc.append_beam(beam_list[i])
            footprint_acc.append_beam(footprint_list[i])
        bl_i = deepcopy(beamline)
        bl_i.get_light_source().set_seed(seed_list[i])
        light_source_acc.append_beamline(bl_i, 
                                         id='beamline seed: %d' % seed_list[i],
                                         weight=1.0)

        if verbose:
            print("Iteration %d: seed=%d, rays=%d" % (i, seed_list[i], beam_list[i].N))

    beamline_acc = S4Beamline()
    beamline_acc.set_light_source(light_source_acc)

    return beamline_acc, beam_acc, footprint_acc


def validate_parallel_beamline(beamline):
    prototype_beamline, _ = _get_parallel_runner_prototype(beamline)
    light_source = prototype_beamline.get_light_source()

    if isinstance(light_source, (SourceGridCartesian, SourceGridPolar)):
        raise ValueError(UNSUPPORTED_PARALLEL_SOURCE_MESSAGE)

    return prototype_beamline


def make_runner_module_from_s4beamline(beamline, module_path=None, verbose=False):
    validate_parallel_beamline(beamline)
    code_text = beamline.to_python_code()
    light_source = beamline.get_light_source()
    default_seed = int(light_source.get_seed())
    default_nrays = _get_default_nrays(light_source, code_text)

    patched_code, nrays_replacements = re.subn(
        r"(\bnrays\s*=\s*)[-+]?\d+",
        r"\1nrays",
        code_text,
        count=1,
    )
    patched_code, seed_replacements = re.subn(
        r"(\bseed\s*=\s*)[-+]?\d+",
        r"\1seed",
        patched_code,
        count=1,
    )

    if seed_replacements != 1:
        raise ValueError("Expected exactly one source seed assignment, found %d." % seed_replacements)

    if nrays_replacements != 1:
        raise ValueError("Expected exactly one source nrays assignment, found %d." % nrays_replacements)

    body = textwrap.indent(patched_code.strip(), "    ")
    runner_source = f"""# Auto-generated from Shadow4 beamline.to_python_code().
# This module is intentionally standalone so joblib/loky workers do not pickle OASYS objects.
# Workers return seed, beam, footprint. Beamline entries are rebuilt in the parent process.

def run_beamline(seed={default_seed}, nrays={default_nrays}):
    if nrays is None:
        nrays = {default_nrays}

{body}

    if "footprint" not in locals():
        footprint = None

    beam.clean_lost_rays()
    if footprint is not None:
        footprint.clean_lost_rays()

    if {bool(verbose)!r}:
        print("seed:", seed, "rays:", beam.N)

    return seed, beam, footprint
"""

    if module_path is None:
        module_path = pathlib.Path(tempfile.gettempdir()) / (
            "runner_from_oasys_%d.py" % os.getpid()
        )

    module_path = pathlib.Path(module_path).resolve()
    module_path.write_text(runner_source, encoding="utf-8")

    return module_path


def make_parallel_runner_module_from_s4beamline(
    beamline,
    module_path=None,
    verbose=False,
    number_of_repetitions=None,
    number_of_rays=None,
    n_jobs=-1,
    output_file="s4_beam.h5",
):

    if module_path is None:
        module_path = pathlib.Path(tempfile.gettempdir()) / (
            "parallel_runner_from_oasys_%d.py" % os.getpid()
        )

    prototype_beamline, number_of_repetitions_from_beamline = _get_parallel_runner_prototype(beamline)
    validate_parallel_beamline(prototype_beamline)
    code_text = prototype_beamline.to_python_code()
    light_source = prototype_beamline.get_light_source()
    default_seed = int(light_source.get_seed())
    default_nrays = _get_default_nrays(light_source, code_text)
    default_number_of_repetitions = (
        int(number_of_repetitions)
        if number_of_repetitions is not None
        else int(number_of_repetitions_from_beamline)
    )
    default_number_of_rays = (
        int(number_of_rays)
        if number_of_rays is not None
        else int(default_nrays)
    )
    default_n_jobs = int(n_jobs)

    patched_code, nrays_replacements = re.subn(
        r"(\bnrays\s*=\s*)[-+]?\d+",
        r"\1nrays",
        code_text,
        count=1,
    )
    patched_code, seed_replacements = re.subn(
        r"(\bseed\s*=\s*)[-+]?\d+",
        r"\1seed",
        patched_code,
        count=1,
    )

    if seed_replacements != 1:
        raise ValueError("Expected exactly one source seed assignment, found %d." % seed_replacements)

    if nrays_replacements != 1:
        raise ValueError("Expected exactly one source nrays assignment, found %d." % nrays_replacements)

    body = textwrap.indent(patched_code.strip(), "    ")
    runner_source = f'''# Auto-generated from Shadow4 beamline.to_python_code().
# This module is intentionally standalone and can be run from a terminal:
#     python {pathlib.Path(module_path).name}

import multiprocessing
import os
import time

import joblib
from joblib import Parallel, delayed


def cpu_info_text():
    lines = [
        "CPU availability:",
        "    os.cpu_count(): %s" % os.cpu_count(),
        "    multiprocessing.cpu_count(): %s" % multiprocessing.cpu_count(),
        "    joblib.cpu_count(): %s" % joblib.cpu_count(),
    ]

    try:
        lines.append("\\n    CPU affinity: %s" % len(os.sched_getaffinity(0)))
    except AttributeError:
        lines.append("    CPU affinity: not available on this OS")

    return "\\n".join(lines)


def print_cpu_info():
    text = cpu_info_text()
    print(text)
    return text


def runner_module_path():
    file_name = globals().get("__file__")
    if file_name is None:
        return "<interactive OASYS script>"
    return os.path.abspath(file_name)


def seed_for_iteration(base_seed, iteration):
    if base_seed == 0:
        return 0
    return int(base_seed + iteration * 2)


def run_beamline(seed={default_seed}, nrays={default_nrays}):
    if nrays is None:
        nrays = {default_nrays}

{body}

    if "footprint" not in locals():
        footprint = None

    beam.clean_lost_rays()
    if footprint is not None:
        footprint.clean_lost_rays()

    if {bool(verbose)!r}:
        print("seed:", seed, "rays:", beam.N)

    return seed, beam, footprint


def concatenate_shadow_data(beam_list, footprint_list, seed_list, verbose=True):
    ntimes = len(seed_list)
    for i in range(ntimes):

        beam_list[i].clean_lost_rays()
        if footprint_list[i] is not None:
            footprint_list[i].clean_lost_rays()

        if i == 0:
            beam_acc = beam_list[i].duplicate()
            footprint_acc = None if footprint_list[i] is None else footprint_list[i].duplicate()
        else:
            beam_acc.append_beam(beam_list[i])
            if footprint_acc is not None and footprint_list[i] is not None:
                footprint_acc.append_beam(footprint_list[i])

        if verbose:
            print("Iteration %d: seed=%d, rays=%d" % (i, seed_list[i], beam_list[i].N))

    return beam_acc, footprint_acc


def run_parallel(number_of_repetitions={default_number_of_repetitions}, number_of_rays={default_number_of_rays}, n_jobs={default_n_jobs}):
    t_total = time.perf_counter()

    print_cpu_info()
    print("")
    print("Number of repetitions:", number_of_repetitions)
    print("Number of rays:", number_of_rays)
    if n_jobs == -1:
        n_jobs = joblib.cpu_count()
    print("Number of cores:", n_jobs)

    print("")
    print("Runner module:", runner_module_path())
    print("")

    base_seed = {default_seed}
    seed_list = [seed_for_iteration(base_seed, i) for i in range(number_of_repetitions)]

    t_parallel = time.perf_counter()
    results = Parallel(n_jobs=n_jobs, backend="loky")(
        delayed(run_beamline)(seed=seed, nrays=number_of_rays)
        for seed in seed_list
    )
    parallel_elapsed = time.perf_counter() - t_parallel

    seed_list = [result[0] for result in results]
    beam_list = [result[1] for result in results]
    footprint_list = [result[2] for result in results]

    t_concatenate = time.perf_counter()
    beam_acc, footprint_acc = concatenate_shadow_data(
        beam_list,
        footprint_list,
        seed_list,
        verbose=True,
    )
    concatenate_elapsed = time.perf_counter() - t_concatenate

    print("")
    print("Parallel elapsed: %.3f s" % parallel_elapsed)
    print("Concatenation elapsed: %.3f s" % concatenate_elapsed)
    print("Total elapsed: %.3f s" % (time.perf_counter() - t_total))
    print("Accumulated rays:", beam_acc.N)

    return beam_acc, footprint_acc


if __name__ == "__main__":
    number_of_repetitions = {default_number_of_repetitions}
    number_of_rays = {default_number_of_rays}
    n_jobs = {default_n_jobs}
    output_file = {output_file!r}

    beam_acc, footprint_acc = run_parallel(
        number_of_repetitions=number_of_repetitions,
        number_of_rays=number_of_rays,
        n_jobs=n_jobs,
    )

    beam_acc.write_h5(
        output_file,
        overwrite=True,
        simulation_name="run001",
        beam_name="begin",
    )

    print("")
    print("Output file:", output_file)
'''

    module_path = pathlib.Path(module_path).resolve()
    module_path.write_text(runner_source, encoding="utf-8")

    return module_path


def load_runner_module(module_path):
    module_path = pathlib.Path(module_path).resolve()
    module_dir = str(module_path.parent)
    module_name = module_path.stem

    if module_dir not in sys.path:
        sys.path.insert(0, module_dir)

    importlib.invalidate_caches()
    if module_name in sys.modules:
        del sys.modules[module_name]

    return importlib.import_module(module_name)


def _get_parallel_runner_prototype(beamline):
    light_source = beamline.get_light_source()

    if isinstance(light_source, S4LightSourceFromBeamlines):
        beamlines = light_source._beamlines

        if len(beamlines) == 0:
            raise ValueError("Accumulated beamline has no child beamlines.")

        return beamlines[0], len(beamlines)

    return beamline, 1


def _get_default_nrays(light_source, code_text):
    if hasattr(light_source, "get_nrays"):
        return int(light_source.get_nrays())

    nrays_match = re.search(r"\bnrays\s*=\s*([-+]?\d+)", code_text)
    if nrays_match is None:
        raise ValueError("Could not determine the number of rays from the light source.")

    return int(nrays_match.group(1))
