#!/usr/bin/env python

from sys import argv

from setuptools import setup

from setup_util.setup_commons import (
    path, parse_requirements, platform, update_variables, get_version,
    get_long_description, find_required_packages, PyTest, PyInstaller,
    move_wheel, print_errors)
from setup_util.taskcollector_builder import TaskCollectorBuilder

from golem.docker.manager import DockerManager
from golem.tools.ci import in_appveyor, in_travis

building_wheel = 'bdist_wheel' in argv
building_binary = 'pyinstaller' in argv

directory = path.abspath(path.dirname(__file__))
requirements, dependencies = parse_requirements(directory)
task_collector_err = TaskCollectorBuilder().build()

update_variables()

setup(
    name='golem',
    version=get_version(),
    platforms=platform,
    description='Global, open sourced, decentralized supercomputer',
    long_description=get_long_description(directory),
    url='https://golem.network',
    author='Golem Team',
    author_email='contact@golem.network',
    license="GPL-3.0",
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Natural Language :: English',
        'Programming Language :: Python :: 2.7',
    ],
    zip_safe=False,
    keywords='golem',
    packages=find_required_packages(),
    install_requires=requirements,
    dependency_links=dependencies,
    # @todo remove test dependencies from requirements.txt and add here
    # extras_require={
    #     'dev': ['check-manifest'],
    #     'test': ['coverage'],
    # },
    include_package_data=True,
    cmdclass={
        'test': PyTest,
        'pyinstaller': PyInstaller
    },
    test_suite='tests',
    tests_require=['mock', 'pytest'],
    entry_points={
        'gui_scripts': [
            'golemapp = golemapp:start',
        ],
        'console_scripts': [
            'golemcli = golemcli:start',
        ]
    },
    data_files=[
        (path.normpath('../../'), [
            'golemapp.py', 'golemcli.py', 'loggingconfig.py'
        ]),
        (path.normpath('../../golem/apps'), [
            path.normpath('apps/registered.ini'),
            path.normpath('apps/images.ini')
        ]),
        (path.normpath('../../golem/apps/rendering/benchmark/minilight'), [
            path.normpath('apps/rendering/benchmark/minilight/cornellbox.ml.txt'),
        ]),
        (path.normpath('../../golem/apps/blender/resources/scripts'), [
            path.normpath('apps/blender/resources/scripts/blendercrop.py.template'),
            path.normpath('apps/blender/resources/scripts/docker_blendertask.py')
        ]),
        (path.normpath('../../golem/apps/lux/resources/scripts'), [
            path.normpath('apps/lux/resources/scripts/docker_luxtask.py'),
            path.normpath('apps/lux/resources/scripts/docker_luxmerge.py')
        ]),
        (path.normpath('../../golem/apps/dummy/resources/scripts'), [
            path.normpath('apps/dummy/resources/scripts/docker_dummytask.py')
        ]),
        (path.normpath('../../golem/apps/dummy/resources/code_dir'), [
            path.normpath('apps/dummy/resources/code_dir/computing.py')
        ]),
        (path.normpath('../../golem/apps/dummy/test_data'), [
            path.normpath('apps/dummy/test_data/in.data')
        ]),
    ]
)

if not (in_appveyor() or in_travis() or
        building_wheel or building_binary):
    DockerManager.pull_images()

if building_wheel:
    move_wheel()


print_errors(task_collector_err)
