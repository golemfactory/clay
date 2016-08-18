import ctypes
import os
import pkgutil
import requests
import shutil
import subprocess
import sys
import time
from distutils import dir_util
from zipimport import zipimporter

from cx_Freeze import Executable
from setuptools import Command


def get_platform():
    if sys.platform.startswith('win') or sys.platform.startswith('nt'):
        return 'win'
    elif sys.platform.startswith('linux'):
        return 'linux'
    elif sys.platform.startswith('darwin'):
        return 'osx'
    else:
        raise EnvironmentError("Unsupported platform: {}".format(sys.platform))


class ModulePackage(object):
    def __init__(self, name, to_lib_dir=True,
                 exclude_platforms=None,
                 include_platforms=None,
                 location_resolver=None):

        self.name = name
        self.include_platforms = include_platforms or []
        self.exclude_platforms = exclude_platforms or []
        self.location_resolver = location_resolver
        self.use_lib_dir = to_lib_dir

    def skip_platform(self, platform):
        if self.include_platforms:
            return platform not in self.include_platforms
        elif self.exclude_platforms:
            return platform in self.exclude_platforms
        return False

    def __str__(self):
        return self.name


class ZippedPackage:
    def __init__(self, name, exclude, in_lib_dir=False):
        self.name = name
        self.exclude = exclude
        self.in_lib_dir = in_lib_dir


class Either(object):
    def __init__(self, *args, **kwargs):
        self.args = args or []
        self.name = kwargs.pop('name', None)

    def __iter__(self):
        for x in self.args:
            yield x

    def __str__(self):
        return repr(self.args)

    @staticmethod
    def iter(arg):
        if isinstance(arg, Either):
            return arg
        return [arg]

    @staticmethod
    def name(arg):
        if isinstance(arg, Either):
            return arg.name
        return None


class PackageCreator(Command):

    user_options = [
        ("unpack-file=", None, "Zip package file to extract"),
        ("pack-modules=", None, "System modules to copy"),
        ("copy-files=", None, "Copy files from modules"),
    ]

    lib_paths = {
        'linux': [
            '/lib', '/lib32', '/lib/x86_64-linux-gnu/',
            '/usr/lib', '/usr/local/lib',
            '/usr/lib/x86_64-linux-gnu/', '/usr/libx32/', ''
        ],
        'osx': [],
        'win': []
    }

    py_vd = '.'.join(sys.version.split('.')[:2])
    py_v = py_vd.replace('.', '')
    platform = get_platform()

    setup_dir = None
    init_script = None

    def run(self):

        cmd = ['python', 'setup.py', 'build_exe']
        if self.platform != 'linux':
            cmd += ['--init-script', self.init_script]

        os.chdir(self.setup_dir)

        import subprocess
        subprocess.check_call(cmd)

        base_dir = os.path.join(self.setup_dir, 'build')
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

        exe_dirs = self._find_exe_dirs(base_dir)

        for _exe_dir in exe_dirs:
            exe_dir = os.path.join(base_dir, _exe_dir)
            lib_dir = os.path.join(exe_dir, 'lib')

            x_dir = self._extract_modules(exe_dir, lib_dir)
            if not x_dir:
                raise EnvironmentError("Invalid module archive")

            self._pack_modules(exe_dir, lib_dir, x_dir)
            self._copy_files(x_dir)
            self._create_files(exe_dir, x_dir)
            self._copy_libs(exe_dir, lib_dir, x_dir)
            self._post_pack(exe_dir, lib_dir, x_dir)

    def initialize_options(self):
        self.extract_modules = None
        self.pack_modules = None
        self.copy_files = None
        self.create_files = None
        self.copy_libs = None
        self.post_pack = None

    def finalize_options(self):

        libs_default = {
            'win': [],
            'linux': [],
            'osx': []
        }

        if not self.extract_modules:
            self.extract_modules = getattr(self.distribution, 'extract_modules', [])
        if not self.pack_modules:
            self.pack_modules = getattr(self.distribution, 'pack_modules', [])
        if not self.create_files:
            self.create_files = getattr(self.distribution, 'create_files', [])
        if not self.copy_files:
            self.copy_files = getattr(self.distribution, 'copy_files', [])
        if not self.copy_libs:
            libs_default.update(getattr(self.distribution, 'copy_libs', {}))
            self.copy_libs = libs_default
        if not self.post_pack:
            self.post_pack = getattr(self.distribution, 'post_pack', [])

    def _extract_modules(self, exe_dir, lib_dir):
        for zipped in self.extract_modules:

            name = zipped.name
            exclude = zipped.exclude
            src_dir = lib_dir if zipped.in_lib_dir else exe_dir

            src_file = os.path.join(src_dir, name)
            dest_dir = ''.join('python' + self.py_v)
            dest_path = os.path.join(lib_dir, dest_dir)

            if os.path.exists(src_file):
                self._unzip(src_file, dest_path)
                self._clean_zip(src_file, exclude)
                return dest_path

        return None

    def _find_lib(self, lib):
        if not lib:
            return None

        def env_path(env_name):
            ld_path = os.environ.get(env_name, '')
            return ld_path.split(os.path.sep) if ld_path else []

        libname = ctypes.util.find_library(lib)

        if not libname:

            if self.platform == 'linux':
                ld_path = env_path('LD_LIBRARY_PATH') + \
                          self.lib_paths['linux']
            elif self.platform == 'osx':
                ld_path = env_path('DYLD_LIBRARY_PATH') + \
                          self.lib_paths['osx']
            else:
                ld_path = env_path('PATH') + \
                          self.lib_paths['win']

            try_paths = [sys.path, ld_path]

            for paths in try_paths:
                for sys_path in paths:
                    libpath = os.path.join(sys_path, lib)
                    if os.path.exists(libpath):
                        return libpath
        return libname

    def _copy_libs(self, exe_dir, *_):
        libs = self.copy_libs.get(self.platform, [])

        for entry in libs:
            optional = False
            resolved_path = None

            for lib in Either.iter(entry):
                if lib is None:
                    optional = True
                    continue

                if self.platform == 'linux':
                    local_lib = self._ldconfig_lib(lib)
                else:
                    local_lib = lib

                lib_path = self._find_lib(local_lib)

                if lib_path:
                    filename = Either.name(entry) or os.path.basename(lib_path)
                    dst_path = os.path.join(exe_dir, filename)

                    shutil.copy(lib_path, dst_path)
                    #self._remove_duplicate_lib(local_lib, [lib_dir, x_dir])
                    resolved_path = lib_path
                    break

            if not optional and not resolved_path:
                raise EnvironmentError('Library "{}" not found'.format(entry))

    @staticmethod
    def _ldconfig_lib(lib):
        if lib.find('*') != -1:
            base_name = lib.replace('*', '')
            output = None

            try:
                with open(os.devnull, "w") as fnull:
                    proc = subprocess.Popen(('ldconfig', '-v'), stdout=subprocess.PIPE, stderr=fnull)
                    output = subprocess.check_output(('grep', base_name), stdin=proc.stdout)
                    proc.wait()
            except:
                pass

            if output:
                split = output.strip().split('->')
                if len(split) >= 2:
                    return split[0].strip()
            return None
        return lib

    @staticmethod
    def _remove_duplicate_lib(lib, dirs):
        for dir in dirs:
            if lib and dir:
                libpath = os.path.join(dir, lib)
                if os.path.exists(libpath):
                    os.remove(libpath)

    def _create_files(self, exe_dir, x_dir):
        for entry in self.create_files:

            module = entry[0]
            files = entry[1]

            exe_module = os.path.join(exe_dir, module)
            x_module = os.path.join(x_dir, module)

            module_dir = exe_module if len(entry) > 2 else x_module

            for filename, data in files.iteritems():
                file_path = os.path.join(module_dir, filename)
                file_dir = os.path.dirname(file_path)

                if not os.path.exists(file_dir):
                    os.makedirs(file_dir)

                print 'Creating file {}'.format(filename)
                with open(file_path, 'w') as f:
                    f.write(data)

    def _pack_modules(self, exe_dir, lib_dir, x_dir):
        mod_dir = os.path.dirname(os.__file__)

        for module in self.pack_modules:
            if isinstance(module, ModulePackage):
                if module.skip_platform(self.platform):
                    continue
                dst_dir = x_dir if module.use_lib_dir else exe_dir
                self._copy_module(module.name, dst_dir, lib_dir,
                                  module.location_resolver)
            else:
                self._copy_module_str(module, mod_dir, exe_dir)

    def _copy_module_str(self, module, mod_dir, exe_dir):
        src_file = self._get_module_file_path(module, mod_dir)

        if os.path.exists(src_file):
            dest_file = self._get_module_file_path(module, exe_dir)

            if not os.path.exists(dest_file):
                print "Copying module file {}".format(src_file)
                shutil.copy(src_file, dest_file)
        else:
            src_file = os.path.join(mod_dir, module)
            dest_file = os.path.join(exe_dir, module)

            if not os.path.exists(dest_file):
                print "Copying module dir {}".format(src_file)
                dir_util.copy_tree(src_file, dest_file, update=1)

    def _copy_module(self, module, exe_dir, lib_dir, location_resolver=None):
        src_path = self._get_module_path(module, location_resolver)
        dest_dir = os.path.join(exe_dir, module.replace('.', os.path.sep))

        if os.path.isdir(src_path):
            dir_util.copy_tree(src_path, dest_dir, update=1)
        elif os.path.isfile(src_path):
            dest_path = os.path.join(dest_dir, os.path.basename(src_path))
            shutil.copy(src_path, dest_path)

    def _copy_files(self, lib_dir):
        for module, files in self.copy_files.iteritems():
            src_dir = self._get_module_path(module)
            dest_dir = os.path.join(lib_dir, module)

            if src_dir and files:
                for filename in files:
                    src_file_path = os.path.join(src_dir, filename)
                    dest_file_path = os.path.join(dest_dir, filename)
                    file_dir = os.path.dirname(dest_file_path)

                    if not os.path.exists(file_dir):
                        os.makedirs(file_dir)

                    print "Copying file {} to {}".format(src_file_path, dest_file_path)
                    shutil.copy(src_file_path, dest_file_path)

    def _post_pack(self, exe_dir, lib_dir, x_dir):
        for method in self.post_pack:
            method(self, exe_dir, lib_dir, x_dir)

    @staticmethod
    def _clean_zip(src_file, entry):
        import zipfile
        import uuid

        white_list = ['BUILD_CONSTANTS', 'cx_Freeze', entry.split('.')[0]]
        tmp_file = src_file + "-" + str(uuid.uuid4())

        zin = zipfile.ZipFile(src_file, 'r')
        zout = zipfile.ZipFile(tmp_file, 'w')

        for item in zin.infolist():
            buf = zin.read(item.filename)
            for w in white_list:
                if item.filename.startswith(w):
                    zout.writestr(item, buf)

        zout.close()
        zin.close()

        os.remove(src_file)
        shutil.move(tmp_file, src_file)

    @staticmethod
    def _unzip(src_file, dest_path):
        import zipfile
        with zipfile.ZipFile(src_file) as zf:
            if not os.path.exists(dest_path):
                try:
                    os.makedirs(dest_path, 0755)
                except:
                    pass
                zf.extractall(dest_path)

    @staticmethod
    def _get_module_file_path(module, module_dir):
        return os.path.join(module_dir, module + ".py")

    @staticmethod
    def _get_module_path(module, location_resolver=None):
        pkg = pkgutil.find_loader(module)
        if pkg:
            if isinstance(pkg, pkgutil.ImpLoader):
                pkg_path = pkg.filename
                if os.path.isfile(pkg_path):
                    return os.path.dirname(pkg_path)
                return pkg.filename
            elif isinstance(pkg, zipimporter):
                return pkg.archive

        if location_resolver:
            resolved = location_resolver()
            if resolved and os.path.exists(resolved):
                return resolved

        raise EnvironmentError("No such module: {}".format(module))

    @staticmethod
    def _find_exe_dirs(src_dir):
        dir_names = next(os.walk(src_dir))[1]
        return [d for d in dir_names if d.startswith('exe.')]

# cx_Freeze configuration

exe_options = {
    'include_files': ['requirements.txt'],
    "packages": [
        "os", "sys", "pkg_resources", "encodings", "click",
        "bitcoin", "devp2p", "service_identity", "OpenEXR",
        "Crypto", "OpenSSL", "ssl"
    ]
}

linux_exe_options = {
    'bin_includes': [
        'libssl.so',
        'libcrypto.so',
        'libstdc++',
        'libc.so.6',
        'rtld',
        'libIex.so.6',
        'libIlmImf.so.6',
        'libjbig.so.0',
        'libjpeg.so.8',
        'libtiff.so.5',
        'libHalf.so.6',
        'libIlmThread.so.6',
        'libQtCore.so.4',
        'libQtGui.so.4',
        'libQtNetwork.so.4',
        'libQtOpenGL.so.4',
        'libQtScript.so.4',
        'libQtSql.so.4',
        'libQtSvg.so.4',
        'libQtTest.so.4',
        'libQtXml.so.4',
        'libfontconfig.so.1',
        'libaudio.so.2',
        'libSM.so.6',
        'libICE.so.6',
        'libXi.so.6',
        'libXt.so.6',
        'libXrender.so.1'
    ],
    'bin_excludes': [
        'libpthread.so.0'
    ]
}

win_exe_options = {
    'include_files': ['requirements.txt'],
    'include_msvcr': True,
    'bin_includes': [
        'pythoncom' + PackageCreator.py_v + '.dll'
    ]
}

osx_exe_options = {
    'bin_excludes': [
        'libQt.dylib',
        'libQtCore.dylib',
        'libQtGui.dylib',
        'libQtNetwork.dylib',
        'libQtOpenGL.dylib',
        'libQtScript.dylib',
        'libQtSql.dylib',
        'libQtSvg.dylib',
        'libQtTest.dylib',
        'libQtXml.dylib',
    ]
}


def _resolve_vboxapi_location():
    platform = get_platform()

    if platform == 'win':
        vbox_root = os.environ.get('VBOX_MSI_INSTALL_PATH', None) or \
                    os.environ.get('VBOX_INSTALL_PATH', None)
        if vbox_root:
            return os.path.join(vbox_root, 'sdk', 'install', 'vboxapi')
    elif platform == 'osx':
        return '/Library/Python/%s.%s/site-packages'.format(sys.version_info[:2])

    return None


def _osx_bin_rewrite(_from, _to, _bin):
    cmd = ['install_name_tool', '-change', _from, _to, _bin]

    print "Rewriting linked library path {} to {} in {}" \
        .format(_from, _to, _bin)

    os.chmod(_bin, 0777)
    subprocess.check_call(cmd)


def osx_rewrite_lib_paths(creator, exe_dir, lib_dir, *args):
    """
    Rewrites linked Qt library paths. XCode developer tools are required,
    i.e. 'install_name_tool'

    :param platform: current platform
    :param exe_dir: exe build dir
    :param args: ignored
    :return: None
    """

    platform = creator.platform
    py_v = creator.py_v
    if platform != 'osx':
        return

    def _make_path(_lib):
        return os.path.join(exe_dir, _lib)

    def _make_lib_py_path(_lib):
        return os.path.join(lib_dir, 'python' + py_v, 'PyQt4', _lib + '.so')

    rewrite_libs = [
        'QtCore',
        'QtGui',
        'QtNetwork',
        'QtOpenGL',
        'QtScript',
        'QtSql',
        'QtSvg',
        'QtTest',
        'QtXml'
    ]

    dst_dir = ''
    src_dirs = [
        ('/usr/local/opt/qt/lib/QtCore.framework/Versions/4/', _make_path),
        ('/usr/local/lib/{}.framework/Versions/4/{}', _make_path),
        ('/usr/local/lib/{}.framework/Versions/4/{}', _make_lib_py_path)
    ]

    # We're trying to rewrite all versions of Qt 4.x libs
    qt_dirs = [
        '/usr/local/Cellar/qt/'  # Homebrew
    ]

    for qt_dir in qt_dirs:
        qt_versions = next(os.walk(qt_dir))[1]

        for qt_ver in qt_versions:
            qt_ver_dir = os.path.join(qt_dir, qt_ver,
                                      'lib/{}.framework/Versions/4/{}')
            src_dirs.append((qt_ver_dir, _make_path))

    # Rewrite (try to cross-match all libraries)
    for src_dir, path_method in src_dirs:
        for lib in rewrite_libs:
            for other_lib in rewrite_libs:
                if lib == other_lib:
                    continue

                lib_path = path_method(lib)
                src_path = src_dir.replace('{}', other_lib)
                dst_path = os.path.join(dst_dir, other_lib)
                _osx_bin_rewrite(src_path, dst_path, lib_path)


def osx_rewrite_python(creator, exe_dir, *args):
    """
    Rewrites python lib in entrypoint. XCode developer tools are required,
    e.g. 'install_name_tool'

    :param platform: current platform
    :param exe_dir: exe build dir
    :param args: ignored
    :return: None
    """
    platform = creator.platform
    py_vd = creator.py_vd
    if platform != 'osx':
        return

    _osx_bin_rewrite(
        # standard python path
        '/usr/local/Frameworks/Python.framework/Versions/{}/Python'.format(py_vd),
        # copied library name
        'libpython{}.dylib'.format(py_vd),
        # binary path
        os.path.join(exe_dir, 'entrypoint')
    )


def linux_remove_libc(creator, exe_dir, *args):
    if creator.platform == 'linux':
        libc_path = os.path.join(exe_dir, 'libc.so.6')
        os.remove(libc_path)


def win_clean_qt(creator, _, __, x_dir):
    if creator.platform != 'win':
        return

    remove_dirs = ['doc', 'examples', 'plugins']
    qt_dir = os.path.join(x_dir, 'PyQt4')

    for d in remove_dirs:
        dir_util.remove_tree(os.path.join(qt_dir, d))


def all_task_collector(creator, *args):
    tc_dir = os.path.join('gnr', 'taskcollector')
    tc_release_dir = os.path.join(tc_dir, 'Release')

    if creator.platform == 'win':
        tc_exe = os.path.join(tc_release_dir, 'taskcollector.exe')
        if not os.path.exists(tc_exe):
            raise EnvironmentError("Please build the taskcollector manually")
        return

    filename = 'taskcollector'
    tc_path = os.path.join(tc_dir, filename)
    tc_release_path = os.path.join(tc_release_dir, filename)

    if not os.path.exists(tc_release_path):
        cwd = os.getcwd()
        os.chdir(tc_dir)
        subprocess.check_call('make', shell=True)
        os.chdir(cwd)


def all_assemble(creator, _exe_dir, _lib_dir, x_dir, *args):
    from distutils.dir_util import copy_tree
    import zipfile
    import re

    def build_subdir(dir_name):
        return os.path.join(build_dir, dir_name)

    def new_package_subdir(dir_name):
        return os.path.join(pack_dir, dir_name)

    def version_stamp(dir_name):
        git_rev = subprocess.check_output(['git', 'rev-parse', 'HEAD'])
        created = time.time()

        file_path = os.path.join(dir_name, '.version')
        if os.path.exists(file_path):
            os.remove(file_path)

        with open(file_path, 'w') as f:
            f.write(str(created))
            f.write("\n")
            f.write(git_rev)

    def zip_dir(src_dir, zip_handle):
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                zip_handle.write(os.path.join(root, f))

    def assemble_dir(dir_name):

        if os.path.exists(pack_dir):
            shutil.rmtree(pack_dir)

        pack_taskcollector_dir = new_package_subdir(os.path.join(x_dir, taskcollector_dir))
        copy_tree(taskcollector_dir, pack_taskcollector_dir, update=True)

        exe_dir = build_subdir(dir_name)
        pack_exe_dir = new_package_subdir(dir_name)
        pack_scripts_dir = new_package_subdir(scripts_dir)

        os.makedirs(pack_dir)
        os.makedirs(pack_scripts_dir)

        shutil.move(exe_dir, pack_exe_dir)
        copy_tree(runner_scripts_dir, pack_dir, update=True)

        if creator.platform == 'win':
            script = 'golem.sh'
        else:
            script = 'golem.cmd'
        os.remove(os.path.join(pack_dir, script))

        for docker_file in docker_files:
            dst_path = os.path.join(pack_scripts_dir, os.path.basename(docker_file))
            shutil.copy(docker_file, dst_path)

        version_stamp(pack_dir)

        platform_name = re.split('[\.\-]+', dir_name)[1]
        file_name = 'golem-' + platform_name + '.zip'

        cwd = os.getcwd()
        os.chdir(build_dir)

        file_path = file_name

        if os.path.exists(file_path):
            os.remove(file_path)

        zipf = zipfile.ZipFile(file_path, 'w', zipfile.ZIP_DEFLATED)
        zip_dir(package_subdir, zipf)
        zipf.close()

        os.chdir(cwd)

    build_dir = 'build'
    scripts_dir = 'scripts'
    runner_scripts_dir = os.path.join(scripts_dir, 'packaging', 'runner')
    taskcollector_dir = os.path.join('gnr', 'taskcollector', 'Release')

    package_subdir = 'golem'
    pack_dir = build_subdir(package_subdir)
    docker_files = [os.path.join('gnr', 'task', 'images', 'Dockerfile.' + ext)
                    for ext in ['base', 'blender', 'luxrender']]

    sub_dirs = next(os.walk(build_dir))[1]

    for subdir in sub_dirs:
        if subdir.startswith('exe'):
            assemble_dir(subdir)


def all_assets(creator, exe_dir, lib_dir, x_dir):
    from distutils.dir_util import copy_tree

    scripts_dir = os.path.join('gnr', 'task', 'scripts')
    scripts_dest_dir = os.path.join(x_dir, scripts_dir)

    images_dir = os.path.join('gnr', 'ui', 'img')
    images_dest_dir = os.path.join(x_dir, images_dir)

    benchmarks_dir = os.path.join('gnr', 'benchmarks')
    benchmarks_dest_dir = os.path.join(x_dir, benchmarks_dir)

    copy_tree(scripts_dir, scripts_dest_dir, update=True)
    copy_tree(images_dir, images_dest_dir, update=True)
    copy_tree(benchmarks_dir, benchmarks_dest_dir, update=True)

    no_preview_path = os.path.join('gnr', 'ui', 'nopreview.png')
    no_preview_dest_path = os.path.join(x_dir, no_preview_path)

    if os.path.exists(no_preview_dest_path):
        os.remove(no_preview_dest_path)
    shutil.copy(no_preview_path, no_preview_dest_path)


def update_cx_freeze_config(options):
    platform = PackageCreator.platform
    if platform == 'osx':
        options.update(osx_exe_options)
    elif platform == 'win':
        options.update(win_exe_options)
    elif platform == 'linux':
        options.update(linux_exe_options)


base = 'Console'
entrypoint = 'golemapp.py'
update_cx_freeze_config(exe_options)

build_options = {
    "build_exe": exe_options,
    "pack": {
        # Patch missing dependencies
        'pack_modules': [
            ModulePackage('psutil'),
            ModulePackage('cffi'),
            ModulePackage('devp2p'),
            ModulePackage('pycparser'),
            ModulePackage('Crypto'),
            ModulePackage('bitcoin'),
            ModulePackage('click'),
            ModulePackage('docker'),
            ModulePackage('websocket'),
            ModulePackage('PIL'),
            ModulePackage('PyQt4'),
            ModulePackage('certifi'),
            ModulePackage('psutil'),

            ModulePackage('pywintypes', include_platforms=['win']),
            ModulePackage('win32api', include_platforms=['win']),
            ModulePackage('win32com', include_platforms=['win']),
            ModulePackage('winerror', include_platforms=['win']),

            ModulePackage('secp256k1', exclude_platforms=['win']),
            ModulePackage('virtualbox', exclude_platforms=['linux']),
            ModulePackage('vboxapi',
                          exclude_platforms=['linux'],
                          location_resolver=_resolve_vboxapi_location),

            ModulePackage('encodings', to_lib_dir=False),
            ModulePackage('ndg.httpsclient', to_lib_dir=True),
            ModulePackage('zope.interface', to_lib_dir=False),

            # Standard library files
            "_abcoll", "_weakrefset",
            "abc", "copy_reg", "genericpath", "linecache", "os", "posixpath",
            "stat", "types", "codecs", "warnings", "importlib", "UserDict",
            "ssl", "keyword", "heapq", "argparse", "collections",
            "re", "sre_compile", "sre_parse", "sre_constants", "textwrap",
            "gettext", "copy", "locale", "functools", 'pprint'
        ],
        # Extract files zipped by cx_Freeze
        # Files beside *.py may not be resolved from an archive
        'extract_modules': [
            ZippedPackage("python" + PackageCreator.py_v + ".zip",
                          exclude=entrypoint,
                          in_lib_dir=True),
            ZippedPackage("library.zip",
                          exclude=entrypoint,
                          in_lib_dir=False)
        ],
        # Patch missing module files
        'copy_files': {
            'bitcoin': ['english.txt'],
            'gnr': ['logging.ini'],
            'golem': [
                os.path.join('ethereum', 'genesis_golem.json'),
                os.path.join('ethereum', 'mine_pending_transactions.js')
            ]
        },
        # Copy missing libs
        'copy_libs': {
            'win': [
                'libeay32.dll',
                'libgcc_s_dw2-1.dll',
                'libwinpthread-1.dll',
                'msvcp120.dll',
                'msvcr120.dll'
            ],
            'linux': [
                'libstdc++*',
                'libc.so*',
                'libpython2.7.so.1.0',
                'ld-linux-x86-64.so.*',
                'libHalf.so.*',
                'libffi.so.*',
                'libgssapi_krb5.so.*',
                'libz.so.1',
                '_sha3.so',
                'OpenEXR.so',
                'netifaces.so',
                '_cffi_backend.so',
                'libraw.so.*',
                'libgmp.so.*',
                'libpng12.so.0',
                Either('libIlmImf.so.*',
                       'libIlmImf-*'),
                Either('libIlmThread.so.*',
                       'libIlmThread-*'),
                Either('libIex.so.*',
                       'libIex-*'),
                Either('sip.x86_64-linux-gnu.so',
                       'sip.so',
                       name='sip.so'),
                Either('_ssl.so',
                       '_ssl.x86_64-linux-gnu.so',
                       name='_ssl.so'),
                Either('libssl3.so',
                       'libssl.so.*'),
                Either('_ctypes.x86_64-linux-gnu.so',
                       '_ctypes.so',
                       name='_ctypes.so'),
                Either('_multiprocessing.x86_64-linux-gnu.so',
                       '_multiprocessing.so',
                       name='_multiprocessing.so'),
                Either('_sqlite3.x86_64-linux-gnu.so',
                       '_sqlite3.so',
                       name='_sqlite3.so'),
                Either('_psutil_linux.x86_64-linux-gnu.so',
                       '_psutil_linux.so',
                       '/usr/local/lib/python2.7/dist-packages/psutil/_psutil_linux.so',
                       name='_psutil_linux.so'),
                Either('_psutil_posix.x86_64-linux-gnu.so',
                       '_psutil_posix.so',
                       '/usr/local/lib/python2.7/dist-packages/psutil/_psutil_posix.so',
                       name='_psutil_posix.so'),
                Either('datetime.x86_64-linux-gnu.so',
                       'datetime.so',
                       None)  # None = optional
            ],
            'osx': [
                'libpython2.7.dylib'
            ]
        },
        # Create files in modules
        'create_files': [
            ('zope', {
                '__init__.py': ''
            }, False)
        ],
        # Post handlers
        'post_pack': [
            linux_remove_libc,
            win_clean_qt,
            osx_rewrite_lib_paths,
            osx_rewrite_python,
            all_assets,
            all_task_collector,
            all_assemble
        ]
    }
}


def update_setup_config(setup_dir, options=None, cmdclass=None, executables=None):

    init_script = os.path.join(setup_dir, 'scripts', 'packaging',
                               'cx_Freeze', 'initscripts', 'ConsoleCustom.py')

    PackageCreator.init_script = init_script
    PackageCreator.setup_dir = setup_dir

    if options is not None:
        options.update(build_options)

    if cmdclass is not None:
        cmdclass.update({'pack': PackageCreator})

    if executables is not None:
        executables.append(Executable(
            base=base,
            script=entrypoint,
            initScript=init_script,
        ))
