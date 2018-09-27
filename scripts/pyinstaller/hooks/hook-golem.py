from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('golem') + \
                collect_submodules('apps') + \
                ['Cryptodome', 'xml', 'scrypt', 'mock']

datas = [
    ('loggingconfig.py', '.'),
    ('apps/*.ini', 'apps/'),
    ('apps/rendering/benchmark/minilight/cornellbox.ml.txt',
     'apps/rendering/benchmark/minilight/'),
    ('apps/rendering/resources/scripts/runner.py',
     'apps/rendering/resources/scripts/'),
    ('apps/blender/resources/scripts/blendercrop.py.template',
     'apps/blender/resources/scripts/'),
    ('apps/blender/resources/scripts/docker_blendertask.py',
     'apps/blender/resources/scripts/'),
    ('apps/lux/resources/scripts/docker_luxtask.py',
     'apps/lux/resources/scripts/'),
    ('apps/lux/resources/scripts/docker_luxmerge.py',
     'apps/lux/resources/scripts/'),
    ('apps/dummy/resources/scripts/docker_dummytask.py',
     'apps/dummy/resources/scripts/'),
    ('apps/dummy/resources/code_dir/computing.py',
     'apps/dummy/resources/code_dir/'),
    ('apps/dummy/test_data/in.data',
     'apps/dummy/test_data/'),
    ('golem/RELEASE-VERSION', 'golem/'),
    ('golem/TERMS.html', 'golem/'),
    ('golem/database/schemas/*.py', 'golem/database/schemas/'),
    ('golem/network/concent/resources/ssl/certs/*.crt',
     'golem/network/concent/resources/ssl/certs/'),
    ('scripts/create-share.ps1', 'scripts/'),
    ('scripts/get-ip-address.ps1', 'scripts/'),
]
