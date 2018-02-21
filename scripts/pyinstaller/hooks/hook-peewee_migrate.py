from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules('peewee_migrate')
datas = collect_data_files('peewee_migrate')
