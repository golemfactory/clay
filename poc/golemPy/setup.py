#!/usr/bin/env python

import sys
from setuptools import setup
from setuptools.command.test import test as TestCommand


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

# TODO: Refer correct README file here
# with open('README.rst') as readme_file:
#     readme = readme_file.read()

# TODO: We don't have any HISTORY file yet
# with open('HISTORY.rst') as history_file:
#     history = history_file.read().replace('.. :changelog:', '')

requirements = [
    'bitcoin==1.1.39',
    'ecdsa==0.13',
    'ipaddr==2.1.11',
    'netifaces==0.10.4',
    'OpenEXR==1.2.0',
    'paramiko==1.16.0',
    'peewee>=2.4.7',
    'Pillow==3.0.0',
    'psutil',
    'pycrypto',
    'pyelliptic==1.5.7',
    'pysftp==0.2.8',
    'pysha3==0.3',
    'pystun==0.1.0',
    'qt4reactor==1.6',
    'requests==2.8.1',
    'rlp==0.4.3',
    'six==1.10.0',
    'Twisted==15.4.0',
    'wheel==0.24.0',
    'zope.interface==4.1.3',
]

test_requirements = [
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
    packages=[
        'golem',
    ],
    package_dir={'golem':
                 'golem'},
    include_package_data=True,
    install_requires=requirements,
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
