import os
import glob
from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import (
    get_module_file_attribute,
    collect_submodules,
)


hiddenimports = collect_submodules('golem') + \
                collect_submodules('apps') + \
                collect_submodules('dns')

datas = [
    ('loggingconfig.py', '.'),
    ('apps/*.ini', 'apps/'),
    ('apps/core/resources/images/*',
     'apps/core/resources/images/'),
    ('apps/blender/resources/images/*.Dockerfile',
     'apps/blender/resources/images/'),
    ('apps/blender/resources/images/entrypoints/scripts/render_tools/templates/'
        'blendercrop.py.template',
     'apps/blender/resources/images/entrypoints/scripts/render_tools/'
        'templates'),
    ('apps/dummy/resources/images',
     'apps/dummy/resources/'),
    ('apps/dummy/resources/code_dir/computing.py',
     'apps/dummy/resources/code_dir/'),
    ('apps/dummy/test_data/in.data',
     'apps/dummy/test_data/'),
    ('apps/glambda/resources', 'apps/glambda/resources'),
    ('apps/wasm/resources', 'apps/wasm/resources'),
    ('apps/wasm/test_data', 'apps/wasm/test_data'),
    ('golem/CONCENT_TERMS.html', 'golem/'),
    ('golem/RELEASE-VERSION', 'golem/'),
    ('golem/TERMS.html', 'golem/'),
    ('golem/database/schemas/*.py', 'golem/database/schemas/'),
    ('golem/envs/docker/benchmark/cpu/minilight/cornellbox.ml.txt',
     'golem/envs/docker/benchmark/cpu/minilight/'),
    ('golem/network/concent/resources/ssl/certs/*.crt',
     'golem/network/concent/resources/ssl/certs/'),
    ('scripts/docker/create-share.ps1', 'scripts/docker/'),
    ('scripts/docker/get-default-vswitch.ps1', 'scripts/docker/'),
    ('scripts/virtualization/get-virtualization-state.ps1',
     'scripts/virtualization'),
    ('scripts/virtualization/get-hyperv-state.ps1', 'scripts/virtualization')
]

# copy of the native `hooks/hook-numpy.py`, so it will also search DLLs/
binaries = []

if is_win:
    extra_dll_locations = ['DLLs']
    for location in extra_dll_locations:
        dll_glob = os.path.join(os.path.dirname(
            get_module_file_attribute('numpy')), location, "*.dll")
        if glob.glob(dll_glob):
            binaries.append((dll_glob, "."))
