#!/usr/bin/env python

from setuptools import setup

from setup.setup_commons import *
from setup.taskcollector_builder import TaskCollectorBuilder
from sys import argv

requirements, dependencies = parse_requirements(path.dirname(__file__))

ui_err = generate_ui()
docker_err = try_pulling_docker_images()
task_collector_err = TaskCollectorBuilder().build()
setup(
    name='golem',
    version=get_golem_version('bdist_wheel' in argv),
    description='Global, open sourced, decentralized supercomputer',
    long_description=get_long_description(path.abspath(path.dirname(__file__))),
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
    cmdclass={'test': PyTest},
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
        (path.normpath('../../'), ['golemapp.py', 'golemcli.py', 'golemgui.py', 'loggingconfig.py', '.version.ini']),
        (path.normpath('../../golem/apps'), [path.normpath('apps/registered.ini'), path.normpath('apps/images.ini')]),
        (path.normpath('../../golem/apps/blender/resources/scripts'),
         [path.normpath('apps/blender/resources/scripts/blendercrop.py.template'),
          path.normpath('apps/blender/resources/scripts/docker_blendertask.py')]),
        (path.normpath('../../golem/apps/lux/resources/scripts'),
         [path.normpath('apps/lux/resources/scripts/docker_luxtask.py')]),
        (path.normpath('../../golem/gui/view/'), [path.normpath('gui/view/nopreview.png')]),
        (path.normpath('../../golem/gui/view/img'),
         [path.normpath('gui/view/img/favicon-48x48.png'), path.normpath('gui/view/img/favicon-256x256.png'),
          path.normpath('gui/view/img/favicon-32x32.png'), path.normpath('gui/view/img/new.png'),
          path.normpath('gui/view/img/task.png'), path.normpath('gui/view/img/settings.png'),
          path.normpath('gui/view/img/user.png'), path.normpath('gui/view/img/eye.png')]),
    ]
)

print_errors(ui_err, docker_err, task_collector_err)
