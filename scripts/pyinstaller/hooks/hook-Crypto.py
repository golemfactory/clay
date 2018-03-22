# based on
# https://raw.githubusercontent.com/stephenrauch/pyinstaller/dd2522afbcbac0473a19570f5325e9cf4758ee18/PyInstaller/hooks/hook-Cryptodome.py

import os.path
import glob

from PyInstaller.compat import EXTENSION_SUFFIXES
from PyInstaller.utils.hooks import get_module_file_attribute

binaries = []
binary_module_names = (
    'Crypto.Cipher',
    'Crypto.Hash',
    'Crypto.Protocol',
    'Crypto.Util',
)

for module_path in binary_module_names:
    m_dir = os.path.dirname(get_module_file_attribute(module_path))
    for ext in EXTENSION_SUFFIXES:
        module_bin = glob.glob(os.path.join(m_dir, '_*%s' % ext))
        for f in module_bin:
            binaries.append((f, module_path.replace('.', '/')))
