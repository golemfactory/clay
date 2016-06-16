#!/usr/bin/env python

import os
import re
import subprocess
import sys
from os import path
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand


def generate_ui_files():
    ui_path = path.normpath(path.join(path.abspath(path.dirname(__file__)), "gnr/ui"))
    from golem.tools.uigen import gen_ui_files
    gen_ui_files(ui_path)

generate_ui_files()


def try_building_docker_images():
    try:
        subprocess.check_call(["docker", "info"])
    except Exception as err:
        print ""
        print "***************************************************************"
        print "Docker not available, not building images."
        print "Command 'docker info' returned {}".format(err)
        print "***************************************************************"
        print ""
        return
    images_dir = path.join('gnr', 'task')
    with open(path.join(images_dir,  'images.ini')) as f:
        for line in f:
            try:
                image, docker_file, tag = line.split()
                if subprocess.check_output(["docker", "images", "-q", image + ":" + tag]):
                    print "\n Image {} exists - skipping".format(image)
                    continue
                docker_file = path.join(images_dir, path.normpath(docker_file))
                cmd = "docker build -t {}:{} -f {} .".format(image, docker_file)
                print "\nRunning '{}' ...\n".format(cmd)
                subprocess.check_call(cmd.split(" "))
            except ValueError:
                print "Skipping line {}".format(line)
            except subprocess.CalledProcessError as err:
                print "Docker build failed: {}".format(err)
                sys.exit(1)

try_building_docker_images()


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

# TODO: Refer correct README file here
# with open('README.rst') as readme_file:
#     readme = readme_file.read()

# TODO: We don't have any HISTORY file yet
# with open('HISTORY.rst') as history_file:
#     history = history_file.read().replace('.. :changelog:', '')

requirements, dependency_links = parse_requirements('requirements.txt')

test_requirements = [
    'mock',
    'pytest'
]

setup(
    name='golem',
    version='0.1.0',
    description="Golem project.",
    # TODO: Update if README is available
    # long_description=readme + '\n\n' + history,
    author="Golem Team",
    author_email='contact@golemproject.net',
    url='http://golemproject.net',
    packages=find_packages(include=['golem*', 'gnr*']),
    install_requires=requirements,
    include_package_data=True,
    dependency_links=dependency_links,
    # TODO: No license yet
    # license="ISCL",
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
    test_suite='tests',
    tests_require=test_requirements,
    cmdclass={'test': PyTest}
)
