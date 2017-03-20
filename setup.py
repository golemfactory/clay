#!/usr/bin/env python

import os
import re
import subprocess
import sys
from os import path

import imp
from setuptools import find_packages

from setuptools.command.test import test as TestCommand

try:
    from cx_Freeze import setup
    use_cx_Freeze = True
except ImportError:
    from setuptools import setup
    use_cx_Freeze = False

def try_docker():
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


def try_building_docker_images():
    err_msg = try_docker()
    if err_msg:
        return err_msg
    images_dir = 'apps'
    cwd = os.getcwdu()

    with open(path.join(images_dir,  'images.ini')) as f:
        for line in f:
            try:
                image, docker_file, tag = line.split()
                if subprocess.check_output(["docker", "images", "-q", image + ":" + tag]):
                    print "\n Image {} exists - skipping".format(image)
                    continue

                docker_file_dir = path.join(images_dir, os.path.dirname(docker_file))
                os.chdir(docker_file_dir)

                docker_file = path.basename(docker_file)
                cmd = "docker build -t {} -f {} .".format(image, docker_file)
                print "\nRunning '{}' ...\n".format(cmd)
                subprocess.check_call(cmd.split(" "))
                cmd = "docker tag {} {}:{}".format(image, image, tag)
                print "\nRunning '{}' ...\n".format(cmd)
                subprocess.check_call(cmd.split(" "))
            except ValueError:
                print "Skipping line {}".format(line)
            except subprocess.CalledProcessError as err:
                print "Docker build failed: {}".format(err)
                sys.exit(1)
            finally:
                os.chdir(cwd)

def try_pulling_docker_images():
    err_msg = try_docker()
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


docker_err = try_pulling_docker_images()


class PyTest(TestCommand):
    ''' py.test integration with setuptools,
        https://pytest.org/latest/goodpractises.html\
        #integration-with-setuptools-test-commands '''

    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


def parse_requirements(requirements_file):
    requirements = []
    dependency_links = []
    for line in open(path.join(path.dirname(__file__), requirements_file)):
        line = line.strip()
        m = re.match('.+#egg=(?P<package>.+)$', line)
        if m:
            requirements.append(m.group('package'))
            dependency_links.append(line)
        else:
            requirements.append(line)
    return requirements, dependency_links


def find_required_packages():
    if sys.platform.startswith('darwin'):
        return find_packages(exclude=['examples'])
    return find_packages(include=['golem*', 'apps*', 'gui*'])


def current_dir():
    return os.path.dirname(os.path.abspath(__file__))


# TODO: Refer correct README file here
# with open('README.rst') as readme_file:
#     readme = readme_file.read()

# TODO: We don't have any HISTORY file yet
# with open('HISTORY.rst') as history_file:
#     history = history_file.read().replace('.. :changelog:', '')

requirements, dependency_links = parse_requirements('requirements.txt')
test_requirements = ['mock', 'pytest']

options = {}
executables = []
cmdclass = {'test': PyTest}
packages = find_required_packages()

if use_cx_Freeze:

    package_creator = imp.load_source(
        'package_creator',
        os.path.join('scripts', 'packaging', 'package_creator.py')
    )
    package_creator.update_setup_config(
        setup_dir=current_dir(),
        options=options,
        cmdclass=cmdclass,
        executables=executables
    )

setup(
    name='golem',
    version='0.1.0',
    description="Golem project.",
    # TODO: Update if README is available
    # long_description=readme + '\n\n' + history,
    author="Golem Team",
    author_email='contact@golemproject.net',
    url='http://golemproject.net',
    packages=packages,
    entry_points={
        'console_scripts': [
            'golemapp = golemapp:start',
            'golemcli = golemcli:start',
        ]
    },
    install_requires=requirements,
    include_package_data=True,
    dependency_links=dependency_links,
    license="GPL-3.0",
    zip_safe=False,
    keywords='golem',
    # classifiers=[
    #     'Development Status :: 2 - Pre-Alpha',
    #     'Intended Audience :: Developers',
    #     'License :: OSI Approved :: ISC License (ISCL)',
    #     'Natural Language :: English',
    #     "Programming Language :: Python :: 2",
    #     'Programming Language :: Python :: 2.6',
    #     'Programming Language :: Python :: 2.7',
    #     'Programming Language :: Python :: 3',
    #     'Programming Language :: Python :: 3.3',
    #     'Programming Language :: Python :: 3.4',
    # ],
    cmdclass=cmdclass,
    options=options,
    executables=executables,
    test_suite='tests',
    tests_require=test_requirements
)

from gui.view.generateui import generate_ui_files


ui_err = ""

try:
    generate_ui_files()
except EnvironmentError as err:
    ui_err = \
        """
        ***************************************************************
        Generating UI elements was not possible.
        Golem will work only in command line mode.
        Generate_ui_files function returned {}
        ***************************************************************
        """.format(err)


def print_errors(ui_err, docker_err):
    if ui_err:
        print(ui_err)
    if docker_err:
        print(docker_err)

print_errors(ui_err, docker_err)
