#!/usr/bin/env python

from sys import argv

from setuptools import setup

from setup.setup_commons import *
from setup.taskcollector_builder import TaskCollectorBuilder

building_wheel = 'bdist_wheel' in argv
building_binary = 'pyinstaller' in argv

directory = path.abspath(path.dirname(__file__))
requirements, dependencies = parse_requirements(directory)
task_collector_err = TaskCollectorBuilder().build()

if building_wheel or building_binary:
    ui_err = generate_ui()

update_variables()

setup(
    name='golem',
    version=get_version(),
    platforms=platform,
    description='Global, open sourced, decentralized supercomputer',
    long_description=get_long_description(directory),
    url='https://golem.network',
    author='Golem Team',
    author_email='contact@golemproject.net',
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
        (path.normpath('../../golem/apps/core/benchmark/minilight'), [
            path.normpath('apps/core/benchmark/minilight/cornellbox.ml.txt'),
        ]),
        (path.normpath('../../golem/apps/blender/resources/scripts'), [
            path.normpath('apps/blender/resources/scripts/blendercrop.py.template'),
            path.normpath('apps/blender/resources/scripts/docker_blendertask.py')
        ]),
        (path.normpath('../../golem/apps/lux/resources/scripts'), [
            path.normpath('apps/lux/resources/scripts/docker_luxtask.py'),
            path.normpath('apps/lux/resources/scripts/docker_luxmerge.py')
        ]),
        (path.normpath('../../golem/gui/view/'), [
            path.normpath('gui/view/nopreview.png')
        ]),
        (path.normpath('../../golem/gui/view/img'), [
            path.normpath('gui/view/img/' + f) for f in [
                'favicon-256x256.png', 'favicon-48x48.png', 'favicon-32x32.png',
                'settings.png', 'task.png', 'user.png', 'new.png', 'eye.png'
            ]
        ]),
    ]
)

from golem.docker.manager import DockerManager
from golem.tools.ci import in_appveyor, in_travis

if not (in_appveyor() or in_travis() or
        building_wheel or building_binary):
    DockerManager.pull_images()

if not (building_wheel or building_binary):
    ui_err = generate_ui()
elif building_wheel:
    move_wheel()


print_errors(ui_err, task_collector_err)
