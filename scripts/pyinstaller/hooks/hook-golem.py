from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules('golem') + \
                collect_submodules('apps') + \
                collect_submodules('dns') + \
                collect_submodules('os_win') + \
                ['Cryptodome', 'xml', 'scrypt', 'mock']

datas = [
    ('loggingconfig.py', '.'),
    ('apps/entrypoint.sh', 'apps/'),
    ('apps/*.ini', 'apps/'),
    ('apps/core/resources/images/nvgpu.Dockerfile',
     'apps/core/resources/images/'),
    ('apps/rendering/benchmark/minilight/cornellbox.ml.txt',
     'apps/rendering/benchmark/minilight/'),
    ('apps/rendering/resources/scripts/runner.py',
     'apps/rendering/resources/scripts/'),
    ('apps/blender/resources/images/blender_nvgpu.Dockerfile',
     'apps/blender/resources/images/'),
    ('apps/blender/resources/scripts/blendercrop.py.template',
     'apps/blender/resources/scripts/'),
    ('apps/blender/resources/scripts/docker_blendertask.py',
     'apps/blender/resources/scripts/'),
    ('apps/dummy/resources/scripts/docker_dummytask.py',
     'apps/dummy/resources/scripts/'),
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
