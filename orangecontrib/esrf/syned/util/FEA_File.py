"""
FEA_File has moved to srxraylib: use ``from srxraylib.profiles.FEA_File import FEA_File``.

This module only re-exports it, so that existing scripts importing
``orangecontrib.esrf.syned.util.FEA_File`` keep working.
"""
from srxraylib.profiles.FEA_File import *  # noqa: F401,F403
from srxraylib.profiles.FEA_File import FEA_File, read_surface_file, write_surface_file, surface_plot  # noqa: F401
