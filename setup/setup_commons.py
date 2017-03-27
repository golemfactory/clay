from codecs import open
from os import path, walk
from sys import platform

from gui.view.generateui import generate_ui_files
from setuptools import find_packages, Command
from setuptools.command.test import test


class PyTest(test):
    """
    py.test integration with setuptools,
    https://pytest.org/latest/goodpractises.html\
    #integration-with-setuptools-test-commands
    """

    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        test.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        test.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        import sys
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


class PyInstaller(Command):
    description = "run pyinstaller and packaging actions"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    @classmethod
    def run(cls):
        import subprocess
        import shutil

        build_dir = path.join('build')
        dist_dir = path.join('dist')
        taskcollector_dir = path.join('apps', 'rendering', 'resources', 'taskcollector', 'Release')

        for directory in [build_dir, dist_dir]:
            if path.exists(directory):
                shutil.rmtree(directory)

        for spec in ['golemapp.spec', 'golemcli.spec']:
            subprocess.check_call(['python', '-m', 'PyInstaller', spec])

        shutil.copytree(taskcollector_dir, path.join(dist_dir, taskcollector_dir))


def get_long_description(my_path):
    """
    Read readme file
    :return: Content of the README file
    """
    with open(path.join(my_path, 'README.md'), encoding='utf-8') as f:
        read = f.read()
    return read


def find_required_packages():
    if platform.startswith('darwin'):
        return find_packages(exclude=['examples', 'tests'])
    return find_packages(include=['golem*', 'apps*', 'gui*'])


def parse_requirements(my_path):
    """
    Parse requirements.txt file
    :return: [requirements, dependencies]
    """
    import re
    requirements = []
    dependency_links = []
    for line in open(path.join(my_path, 'requirements.txt')):
        line = line.strip()
        m = re.match('.+#egg=(?P<package>.+)$', line)
        if m:
            requirements.append(m.group('package'))
            dependency_links.append(line)
        else:
            requirements.append(line)
    return requirements, dependency_links


def print_errors(*errors):
    for error in errors:
        if error:
            print(error)


def generate_ui():
    try:
        generate_ui_files()
    except EnvironmentError as err:
        return \
            """
            ***************************************************************
            Generating UI elements was not possible.
            Golem will work only in command line mode.
            Generate_ui_files function returned {}
            ***************************************************************
            """.format(err)


def get_golem_version(increase):
    from ConfigParser import ConfigParser
    from golem.core.common import get_golem_path
    from os.path import join
    config = ConfigParser()
    config_path = join(get_golem_path(), '.version.ini')
    config.read(config_path)
    version = config.get('version', 'version')
    if platform.startswith('linux') and increase:    # upgrade version only when building on Linux and building wheel
        v = version.split('.')
        version = "{}.{}.{}".format(v[0], v[1], int(v[2]) + 1)
        v = "[version]\nversion = {}".format(version)
        with open(config_path, 'wb') as f:
            f.write(v)
    return version


def get_files():
    from golem.core.common import get_golem_path
    golem_path = get_golem_path()
    extensions = ['py', 'pyc', 'pyd', 'ini', 'template', 'dll', 'png', 'txt']
    excluded = ['golem.egg-info', 'build', 'tests', 'Installer', '.git']
    beginnig = "../../golem/"
    result = []
    for root, dirs, files in walk('.', topdown=False):
        if root != '.' and root.split(path.sep)[1] in excluded:
            continue
        srcs = []
        if root == '.':
            dst = path.normpath(path.join("../..", root.replace(golem_path, '')))
        else:
            dst = path.normpath(path.join(beginnig, root.replace(golem_path, '')))
        for name in files:
            f_ = "{}/{}".format(root, name)
            if f_.split('.')[-1] in extensions:
                srcs.append(path.normpath(f_.replace(golem_path, '')))
        if len(srcs) > 0:
            result.append((dst, srcs))
    return result
