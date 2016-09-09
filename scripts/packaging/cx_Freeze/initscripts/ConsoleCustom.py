import os
import sys

sys.frozen = True
py_ver = '.'.join(sys.version.split('.')[:2])


def get_platform():
    if sys.platform.startswith('win') or sys.platform.startswith('nt'):
        return 'win'
    elif sys.platform.startswith('linux'):
        return 'linux'
    elif sys.platform.startswith('darwin'):
        return 'osx'
    else:
        raise EnvironmentError("Unsupported platform: {}".format(sys.platform))


def exec_env(var_name, custom_paths):
    prev_var = os.environ.get(var_name, None)
    paths = prev_var.split(os.pathsep) if prev_var else []

    if False in [p in paths for p in custom_paths]:
        paths += custom_paths
        os.environ[var_name] = os.pathsep.join(paths)
        os.execv(sys.executable, sys.argv)
        sys.exit(0)


cur_dir = os.path.abspath(DIR_NAME)
pkg_dir = os.path.join(cur_dir, 'lib')
image_formats_dir = os.path.join(pkg_dir, 'imageformats')
dep_path = os.path.join(pkg_dir, 'python' + py_ver.replace('.', ''))
lib_path = os.path.join(pkg_dir, 'python' + py_ver)

sys.path = [dep_path, cur_dir, INITSCRIPT_ZIP_FILE_NAME]
ld_paths = [cur_dir, pkg_dir, lib_path, image_formats_dir]

platform = get_platform()

if platform == 'linux':
    exec_env('LD_LIBRARY_PATH', ld_paths)
elif platform == 'osx':
    exec_env('DYLD_LIBRARY_PATH', ld_paths)

os.environ["TCL_LIBRARY"] = os.path.join(cur_dir, "tcl")
os.environ["TK_LIBRARY"] = os.path.join(cur_dir, "tk")
os.environ["PYTHONPATH"] = os.pathsep.join(sys.path)
os.environ["PATH"] = os.pathsep.join([cur_dir, os.environ["PATH"]])

m = __import__("__main__")

name, ext = os.path.splitext(os.path.basename(os.path.normcase(FILE_NAME)))
moduleName = "%s__main__" % name

import importlib

module = importlib.import_module(moduleName)
module.start()
