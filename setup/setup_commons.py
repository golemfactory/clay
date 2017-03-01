import subprocess
import sys
from codecs import open
from os import listdir, path
from sys import platform

from setuptools import find_packages
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


def print_errors(ui_err, docker_err, task_err):
    if ui_err:
        print(ui_err)
    if docker_err:
        print(docker_err)
    if task_err:
        print(task_err)


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


def try_pulling_docker_images():
    err_msg = __try_docker()
    if err_msg:
        return err_msg
    images_dir = 'apps'

    with open(path.join(images_dir, 'images.ini')) as f:
        for line in f:
            try:
                image, docker_file, tag = line.split()
                if subprocess.check_output(["docker", "images", "-q", image + ":" + tag]):
                    print("\n Image {} exists - skipping".format(image))
                    continue
                cmd = "docker pull {}:{}".format(image, tag)
                print("\nRunning '{}' ...\n".format(cmd))
                subprocess.check_call(cmd.split(" "))
            except ValueError:
                print("Skipping line {}".format(line))
            except subprocess.CalledProcessError as err:
                print("Docker pull failed: {}".format(err))
                sys.exit(1)


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
    return Repo(get_golem_path()).tags[-2].name  # -2 because of 'brass0.3' tag


def update_ini():
    version_file = path.join(get_golem_path(), '.version.ini')
    file_name_ = file_name().split('-')
    tag = file_name_[1]
    commit = file_name_[2]
    version = "[version]\nversion = {}\n".format(tag + ("-" + commit + "-") if commit.startswith('0x') else "")
    with open(version_file, 'wb') as f_:
        f_.write(version)


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
            plat = "linux_x86_64"
    elif platform.startswith('win'):
        plat = "win32"
    else:
        raise SystemError("Incorrect platform: {}".format(platform))
    if commit_id != tag_id:  # devel package
        return "golem-{}-0x{}{}-cp27-none-{}.whl".format(tag.name, commit_id[:4], commit_id[-4:], plat)
    else:  # release package
        return "golem-{}-cp27-none-{}.whl".format(tag.name, plat)


def __try_docker():
    try:
        subprocess.check_call(["docker", "info"])
    except Exception as err:
        return \
            """
            ***************************************************************
            Docker not available, not building images.
            Golem will not be able to compute anything.
            Command 'docker info' returned {}
            ***************************************************************
            """.format(err)
