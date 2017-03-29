from codecs import open
from os import listdir, path, walk
from sys import platform

from setuptools import find_packages, Command
from setuptools.command.test import test

from golem.core.common import get_golem_path
from gui.view.generateui import generate_ui_files


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


def update_variables():
    import re
    file_ = path.join(get_golem_path(), 'golem', 'core', 'variables.py')
    with open(file_, 'rb') as f_:
        variables = f_.read()
    v = get_version().split('.')
    version = "{}.{}".format(v[0], v[1])
    variables = re.sub(r"APP_VERSION = \".*\"", "APP_VERSION = \"{}\"".format(version), variables)
    with open(file_, 'wb') as f_:
        f_.write(variables)


def move_wheel():
    from shutil import move
    path_ = path.join(get_golem_path(), 'dist')
    files_ = [f for f in listdir(path_) if path.isfile(path.join(path_, f))]
    files_.sort()
    source = path.join(path_, files_[-1])
    dst = path.join(path_, file_name())
    move(source, dst)


def get_version():
    from git import Repo
    return Repo(get_golem_path()).tags[-2].name     # -2 because of 'brass0.3' tag


def file_name():
    """
    Get wheel name
    :return: Name for wheel
    """
    from git import Repo
    repo = Repo(get_golem_path())
    tag = repo.tags[-2]  # get latest tag
    tag_id = tag.commit.hexsha  # get commit id from tag
    commit_id = repo.head.commit.hexsha  # get last commit id
    if platform.startswith('linux'):
        from platform import architecture
        if architecture()[0].startswith('64'):
            plat = "linux_x86_64"
        else:
            plat = "linux_i386"
    elif platform.startswith('win'):
        plat = "win32"
    elif platform.startswith('darwin'):
        plat = "macosx_10_12_x86_64"
    else:
        raise SystemError("Incorrect platform: {}".format(platform))
    if commit_id != tag_id:  # devel package
        return "golem-{}-0x{}{}-cp27-none-{}.whl".format(tag.name, commit_id[:4], commit_id[-4:], plat)
    else:  # release package
        return "golem-{}-cp27-none-{}.whl".format(tag.name, plat)


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
