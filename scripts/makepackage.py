import glob
import shutil
import os
import sys
import py_compile

from golem.core.common import get_golem_path


def make_folder(dest):
    if not os.path.isdir(dest):
        os.mkdir(dest)


def copy_files(dest, src):
    files = glob.glob(os.path.join(src, '*.pyc')) + glob.glob(os.path.join(src, '*.ini'))
    files += glob.glob(os.path.join(src, '*.jpg')) + glob.glob(os.path.join(src, '*.exe'))
    files += glob.glob(os.path.join(src, '*.txt')) + glob.glob(os.path.join(src, '*.dll'))
    files += glob.glob(os.path.join(src, '*.gt'))
    for f in files:
        shutil.copy(f, os.path.join(dest, os.path.basename(f)))


def copy_to_package(dest, src):
    copy_files(dest, src)
    dirs = [name for name in os.listdir(src) if os.path.isdir(os.path.join(src, name))]
    for d in dirs:
        dest_dir = os.path.join(dest, d)
        print dest_dir
        if not os.path.isdir(dest_dir):
            os.mkdir(dest_dir)

        print os.path.join(src, d)
        if os.path.isdir(os.path.join(src, d)):
            copy_to_package(dest_dir, os.path.join(src, d))


def main():
    if len(sys.argv) > 1:
        dest = sys.argv[1]
    else:
        dest = os.getcwd()

    src_path = get_golem_path()
    py_compile.compile(os.path.normpath(os.path.join(src_path, 'gnr/main.py')))
    py_compile.compile(os.path.normpath(os.path.join(src_path, 'gnr/admmain.py')))

    make_folder(dest)
    copy_to_package(dest, src_path)


main()
