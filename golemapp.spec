# -*- mode: python -*-
import os

block_cipher = None


def on_path(app):
    for path in os.environ["PATH"].split(os.pathsep):
        app_path = os.path.join(path.strip('"'), app)
        if os.path.isfile(app_path) and os.access(app_path, os.X_OK):
            return True
    return False


a = Analysis(['golemapp.py'],

             hookspath=['./scripts/pyinstaller/hooks'],

             hiddenimports=[
                 'Cryptodome',
                 'rlp', 'web3', 'pylru', 'xml',
                 'sha3', 'requests', 'scrypt',
                 'OpenEXR', 'Imath'
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
          name='golemapp',
          debug=False,
          strip=False,
          upx=on_path('upx'),
          console=True)
