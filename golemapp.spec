# -*- mode: python -*-
import glob
import os

import sys

block_cipher = None


def tree(directory):

    def glob_dir(_dir):
        return '{}/*'.format(_dir)

    def traverse(_dir):
        files = []
        for entry in glob.glob(_dir):
            if entry.endswith('.pyc') or entry.endswith('.pyd'):
                continue
            elif os.path.isfile(entry):
                files.append(entry)
            elif os.path.isdir(entry):
                files += traverse(glob_dir(entry))
        return files

    return [(f, os.path.dirname(f)) for f in
            traverse(glob_dir(directory))]


hidden_imports = [
    'OpenEXR', 'sha3', 'scrypt',
    'requests', 'web3', 'rlp', 'pylru',
    'Imath'
]

binaries = []

is_windows = sys.platform == 'win32'
icon = None

if is_windows:
    import site
    icon = os.path.join(os.getcwd(), 'Installer', 'favicon.ico')
    try:
        import vboxapi
    except ImportError:
        print('Error importing VirtualBox API. You can install it with:')
        print('python "%VBOX_MSI_INSTALL_PATH%\\sdk\\install\\vboxapisetup.py" install')
        sys.exit(1)

    hidden_imports += ['vboxapi']


a = Analysis(['golemapp.py'],
             hookspath=['./scripts/pyinstaller/hooks'],
             hiddenimports=hidden_imports,
             pathex=[],
             binaries=binaries,
             datas=tree('apps/lux/benchmark') + tree('apps/blender/benchmark'),
             runtime_hooks=[],
             win_no_prefer_redirects=True,
             win_private_assemblies=True,
             cipher=block_cipher)

pyz = PYZ(a.pure,
          a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='golemapp',
          debug=False,
          strip=False,
          upx=False,
          icon=icon,
          console=True)
