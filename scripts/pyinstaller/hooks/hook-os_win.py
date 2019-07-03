from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules('os_win')
#datas = copy_metadata('os_win')
