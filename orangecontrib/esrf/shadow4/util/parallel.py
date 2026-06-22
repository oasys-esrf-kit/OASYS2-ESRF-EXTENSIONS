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


def seed_for_iteration(base_seed, iteration):
    if base_seed == 0:
        return 0
    return int(base_seed + ((iteration + 1) * 2))


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


def make_runner_module_from_s4beamline(beamline, module_path=None, verbose=False):
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
            "parallel_runner_from_oasys_%d.py" % os.getpid()
        )

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


def _get_default_nrays(light_source, code_text):
    if hasattr(light_source, "get_nrays"):
        return int(light_source.get_nrays())

    nrays_match = re.search(r"\bnrays\s*=\s*([-+]?\d+)", code_text)
    if nrays_match is None:
        raise ValueError("Could not determine the number of rays from the light source.")

    return int(nrays_match.group(1))
