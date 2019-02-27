from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('golem') + \
                collect_submodules('apps') + \
                collect_submodules('dns') + \
                collect_submodules('os_win') + \
                ['Cryptodome', 'xml', 'scrypt', 'mock']

datas = [
    ('loggingconfig.py', '.'),
    ('apps/*.ini', 'apps/'),
    ('apps/entrypoint.sh', 'apps/'),
    ('apps/core/resources/images/*',
     'apps/core/resources/images/'),
    ('apps/rendering/benchmark/minilight/cornellbox.ml.txt',
     'apps/rendering/benchmark/minilight/'),
    ('apps/blender/resources/images/*.Dockerfile',
     'apps/blender/resources/images/'),
    ('apps/blender/resources/images/scripts/templates/blendercrop.py.template',
     'apps/blender/resources/images/scripts/templates'),
    ('apps/dummy/resources/images',
     'apps/dummy/resources/'),
    ('apps/dummy/resources/code_dir/computing.py',
     'apps/dummy/resources/code_dir/'),
    ('apps/dummy/test_data/in.data',
     'apps/dummy/test_data/'),
    ('golem/CONCENT_TERMS.html', 'golem/'),
    ('golem/RELEASE-VERSION', 'golem/'),
    ('golem/TERMS.html', 'golem/'),
    ('golem/database/schemas/*.py', 'golem/database/schemas/'),
    ('golem/network/concent/resources/ssl/certs/*.crt',
     'golem/network/concent/resources/ssl/certs/'),
    ('scripts/docker/create-share.ps1', 'scripts/docker/'),
    ('scripts/docker/get-default-vswitch.ps1', 'scripts/docker/'),
    ('scripts/virtualization/get-virtualization-state.ps1',
     'scripts/virtualization')
]
