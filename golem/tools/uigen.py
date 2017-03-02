import os
import subprocess
from contextlib import contextmanager

PYUIC_PATH = "pyuic.py"  # Path to Python User Interface Compiler


@contextmanager
def prepend_pyqt5_path():
    import PyQt5
    qt_path = os.path.dirname(PyQt5.__file__)
    path = os.environ['PATH']

    os.environ['PATH'] = qt_path + os.pathsep + path
    yield
    os.environ['PATH'] = path


def call_pyrcc(py_file, qrc_file):
    with prepend_pyqt5_path():
        subprocess.check_call('pyrcc5 -o ' + py_file + ' ' + qrc_file, shell=True)


def regenerate_ui_files(root_path):
    """ Find all files in given directory that ends with ".ui" and have later date than generated user interfaces python
    files and generate new user interface files from them. New files will be placed in root path in gen directory.
    :param dir root_path: directory where interface files are placed
    """
    dirs = [name for name in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, name))]
    files = [name for name in os.listdir(root_path) if os.path.isfile(os.path.join(root_path, name))]
    pyuic_path = PYUIC_PATH

    for dir_ in dirs:
        regenerate_ui_files(os.path.join(root_path, dir_))

    pth, filename = os.path.split(os.path.realpath(__file__))
    pyuic_path = os.path.join(pth, pyuic_path)
    for file_ in files:
        if file_.endswith(".qrc"):
            out_file = os.path.join(root_path, "gen", file_[:-4] + "_rc.py")
            call_pyrcc(out_file, os.path.join(root_path, file_), )

    for file_ in files:
        if file_.endswith(".ui"):
            out_file = os.path.join("gen", "ui_" + file_[0:-3] + ".py")
            out_file_path = os.path.join(root_path, out_file)

            if os.path.exists(out_file_path) and not os.path.isdir(out_file_path):
                if os.path.getmtime(out_file_path) > os.path.getmtime(os.path.join(root_path, file_)):
                    if os.path.getsize(out_file_path) > 0:
                        continue

            if not os.path.exists(pyuic_path):
                raise IOError("Can't open file " + pyuic_path)

            cmd = ["python", pyuic_path, os.path.join(root_path, file_)]
            print cmd
            result = subprocess.check_output(cmd)
            with open(os.path.join(root_path, out_file), 'w') as f:
                f.write(result)


def gen_ui_files(path):
    """ If path doesn't exist throw IOError. Otherwise regenerate all user interface python files that may be
    needed. Find all files in given path that ends with ui and compare their date with generated python user interface
    files with similiar name. If ui files are newer that regenerate python user interface files (generate new if they
    don't exist). If they are older don't do anything.
    :param str path: path to directory where ui files are placed
    """
    if os.path.exists(path):
        regenerate_ui_files(path)
    else:
        cwd = os.getcwd()
        raise IOError("uigen: Cannot find {} dir or wrong working directory: {}".format(path, cwd))
