from PyInstaller.utils.hooks import collect_data_files, collect_submodules

hiddenimports = collect_submodules('golem') + \
                collect_submodules('gui') + \
                collect_submodules('apps') + ['Cryptodome', 'xml', 'scrypt']

datas = collect_data_files('gui') + [
    ('loggingconfig.py', '.'),
    ('gui/view/*', 'gui/view'),
    ('apps/*.ini', 'apps'),
    ('apps/core/benchmark/minilight/cornellbox.ml.txt', 'apps/core/benchmark/minilight'),
    ('apps/blender/resources/scripts/blendercrop.py.template', 'apps/blender/resources/scripts/'),
    ('apps/blender/resources/scripts/docker_blendertask.py', 'apps/blender/resources/scripts/'),
    ('apps/lux/resources/scripts/docker_luxtask.py', 'apps/lux/resources/scripts/'),
    ('apps/lux/resources/scripts/docker_luxmerge.py', 'apps/lux/resources/scripts/'),
]
