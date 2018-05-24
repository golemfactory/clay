from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files('golem_verificator', include_py_files=True)
