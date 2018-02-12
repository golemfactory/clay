#!/usr/bin/env python

import sys

from setuptools import setup

from setup_util.setup_commons import (
    path, parse_requirements, get_version,
    get_long_description, find_required_packages, PyInstaller,
    move_wheel, print_errors, DatabaseMigration)
from setup_util.taskcollector_builder import TaskCollectorBuilder

from golem.docker.manager import DockerManager
from golem.tools.ci import in_appveyor, in_travis

building_wheel = 'bdist_wheel' in sys.argv
building_binary = 'pyinstaller' in sys.argv
building_migration = 'migration' in sys.argv

directory = path.abspath(path.dirname(__file__))
requirements, dependencies = parse_requirements(directory)
task_collector_err = TaskCollectorBuilder().build()

setup(
    name='golem',
    version=get_version(),
    platforms=sys.platform,
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
    include_package_data=True,
    cmdclass={
        'pyinstaller': PyInstaller,
        'migration': DatabaseMigration
    },
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

if not building_migration:
    from golem.database.migration.create import latest_migration_exists
    if not latest_migration_exists():
        raise RuntimeError("Database schema error: latest migration script "
                           "does not exist")

print_errors(task_collector_err)
