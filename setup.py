#! /usr/bin/env python3

# coding: utf-8
# /*##########################################################################
#
# Copyright (c) 2025 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ###########################################################################*/

#
# Memorandum: 
#
# Install from sources: 
#     git clone https://github.com/oasys-kit-esrf/OASYS2-ESRF-EXTENSIONS
#     cd OASYS2-ESRF-EXTENSIONS
#     python -m pip install -e . --no-deps --no-binary :all:
#
# Upload to pypi (when uploading, increment the version number):
#     python setup.py register (only once, not longer needed)
#     # use python > 3.10, pip > 25.2 (packages needed: twine build)
#     rm -fR dist
#     python setup.py sdist
#     python -m build
#     python -m twine upload dist/*
#
# Install from pypi:
#     pip install OASYS2-ESRF-EXTENSIONS
#

__authors__ = ["M Sanchez del Rio, Juan Reyes-Herrera, Rafael Celestre"]
__license__ = "MIT"
__date__ = "04/11/2025"

import os
import sys
from setuptools import find_packages, setup

NAME = 'OASYS2-ESRF-EXTENSIONS'
VERSION = '0.0.1'
ISRELEASED = False

DESCRIPTION = 'oasys2-esrf-extensions'
README_FILE = os.path.join(os.path.dirname(__file__), 'README.md')
LONG_DESCRIPTION = open(README_FILE).read()
AUTHOR = 'M Sanchez del Rio, Juan Reyes-Herrera, Rafael Celestre'
AUTHOR_EMAIL = 'srio@esrf.eu'
URL = 'https://github.com/oasys-esrf-kit/OASYS2-ESRF-EXTENSIONS'
DOWNLOAD_URL = 'https://github.com/oasys-esrf-kit/OASYS2-ESRF-EXTENSIONS'
LICENSE = __license__

KEYWORDS = [
    'ray tracing',
    'wave optics',
    'x-ray optics',
    'oasys2',
    ]

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Environment :: X11 Applications :: Qt',
    'Environment :: Console',
    'Environment :: Plugins',
    'Programming Language :: Python :: 3',
    'Intended Audience :: Science/Research',
    ]


SETUP_REQUIRES = (
                  'setuptools',
                  )

INSTALL_REQUIRES = (
                    'oasys2>=0.0.19',
                    # 'pandas',
                    # 'numba',
                    # 'accelerator-toolbox==0.6.1',
                    # 'oasys-barc4ro>=2024.11.13',
                    # 'crystalpy>=0.0.25',  # todo: remove?, base lib of oasys2
                    # 'shadow4>=0.1.70',
                    # 'xoppylib>=1.0.46',
                    )

PACKAGES = find_packages(exclude=('*.tests', '*.tests.*', 'tests.*', 'tests'))

PACKAGE_DATA = {
    "orangecontrib.esrf.oasys.widgets.extension":["icons/*.png", "icons/*.jpg"],
    "orangecontrib.esrf.syned.widgets.extension": ["icons/*.png", "icons/*.jpg"],
    "orangecontrib.esrf.xoppy.widgets.extension": ["icons/*.png", "icons/*.jpg"],
    "orangecontrib.esrf.shadow4.widgets.extension": ["icons/*.png", "icons/*.jpg", "miscellanea/*.txt"],
    "orangecontrib.esrf.wofry.widgets.extension":["icons/*.png", "icons/*.jpg"],
    "orangecontrib.esrf.srw.widgets.extension":["icons/*.png", "icons/*.jpg"],
    }

ENTRY_POINTS = {
    'oasys2.addons' : (
                        "ESRF = orangecontrib.esrf",
                        # "Oasys ESRF Extension = orangecontrib.esrf.oasys",
                        # "Syned ESRF Extension = orangecontrib.esrf.syned",
                        # "XOPPY ESRF Extension = orangecontrib.esrf.xoppy",
                        # "Shadow ESRF Extension = orangecontrib.esrf.shadow4",
                        # "Wofry ESRF Extension = orangecontrib.esrf.wofry",
                        # "SRW ESRF Extension = orangecontrib.esrf.srw",
                       ),
    'oasys2.widgets' : (
                        # "ESRF wofry = orangecontrib.esrf.wofry.widgets.extension",
                        "ESRF Oasys   = orangecontrib.esrf.oasys.widgets.extension",
                        "ESRF Syned   = orangecontrib.esrf.syned.widgets.extension",
                        "ESRF XOPPY   = orangecontrib.esrf.xoppy.widgets.extension",
                        "ESRF Shadow4 = orangecontrib.esrf.shadow4.widgets.extension",
                        "ESRF Wofry   = orangecontrib.esrf.wofry.widgets.extension",
                        "ESRF SRW     = orangecontrib.esrf.srw.widgets.extension",
                        ),
    # 'oasys2.menus' : ("esrfmenu = orangecontrib.esrf.menu",)
    }

if __name__ == '__main__':
    setup(
          name = NAME,
          version = VERSION,
          description = DESCRIPTION,
          long_description = LONG_DESCRIPTION,
          long_description_content_type='text/markdown',
          author = AUTHOR,
          author_email = AUTHOR_EMAIL,
          url = URL,
          download_url = DOWNLOAD_URL,
          license = LICENSE,
          keywords = KEYWORDS,
          classifiers = CLASSIFIERS,
          packages = PACKAGES,
          package_data = PACKAGE_DATA,
          setup_requires = SETUP_REQUIRES,
          install_requires = INSTALL_REQUIRES,
          entry_points = ENTRY_POINTS,
          include_package_data = True,
          zip_safe = False,
          )
