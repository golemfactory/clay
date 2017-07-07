# -*- mode: python -*-
import os
import sys

block_cipher = None
icon = None

if sys.platform == 'win32':
    icon = os.path.join(os.getcwdu(), 'Installer', 'favicon.ico')

a = Analysis(['golemcli.py'],
             hookspath=['./scripts/pyinstaller/hooks'],
             hiddenimports=[],
             excludes=[
                 'PyQt5', 'sip'
             ],
             pathex=[],
             binaries=[],
             datas=[],
             runtime_hooks=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure,
          a.zipped_data,
          cipher=block_cipher)

exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='golemcli',
          debug=False,
          strip=False,
          upx=False,
          icon=icon,
          console=True)
