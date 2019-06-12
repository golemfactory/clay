# -----------------------------------------------------------------------------
# Copyright (c) 2013-2018, PyInstaller Development Team.
#
# Distributed under the terms of the GNU General Public License with exception
# for distributing bootloader.
#
# The full license is in the file COPYING.txt, distributed with this software.
# -----------------------------------------------------------------------------
# If numpy is built with MKL support it depends on a set of libraries loaded
# at runtime. Since PyInstaller's static analysis can't find them they must be
# included manually.
#
# See
# https://github.com/pyinstaller/pyinstaller/issues/1881
# https://github.com/pyinstaller/pyinstaller/issues/1969
# for more information
import os
import os.path
import re
from PyInstaller.utils.hooks import get_package_paths
from PyInstaller import log as logging
from typing import List

binaries: List = []

logger = logging.getLogger(__name__)

# look for libraries in numpy package path
pkg_base, pkg_dir = get_package_paths('numpy')
dll_dir = os.path.join(pkg_dir, 'DLLs')
logger.info("pkg_base=%r, pkg_dir=%r, dll_dir=%r", pkg_base, pkg_dir, dll_dir)
if os.exists(dll_dir):
    re_anylib = re.compile(r'\w+\.(?:dll|so|dylib)', re.IGNORECASE)
    dlls_pkg = [f for f in os.listdir(dll_dir) if re_anylib.match(f)]
    logger.info("dlls_pkg=%r", dlls_pkg)
    binaries += [(os.path.join(dll_dir, f), '.') for f in dlls_pkg]
