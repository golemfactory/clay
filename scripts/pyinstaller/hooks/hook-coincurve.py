from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

dylibs = collect_dynamic_libs('coincurve._libsecp256k1')
datas = collect_data_files('coincurve')
