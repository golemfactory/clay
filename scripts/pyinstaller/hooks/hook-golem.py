from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules('golem') + \
                collect_submodules('gui') + \
                collect_submodules('apps')

datas = collect_data_files('gui') + [
    ('logging.ini', '.'),
    ('gui/view/*', 'gui/view'),
    ('apps/*.ini', 'apps'),
    ('apps/blender/resources/scripts/blendercrop.py.template', 'apps/blender/resources/scripts/'),
]
