#!/usr/bin/env python

from setuptools import setup

from setup.setup_commons import *
from setup.taskcollector_builder import TaskCollectorBuilder


requirements, dependencies = parse_requirements(path.dirname(__file__))

ui_err = generate_ui()
docker_err = try_pulling_docker_images()
task_collector_err = TaskCollectorBuilder().build()

setup(
    name='golem',
    version='0.1.0',
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
    # @todo is it necessary?
    # options=options,
    # executables=executables,
    test_suite='tests',
    tests_require=['mock', 'pytest'],
    entry_points={
        'console_scripts': [
            'golemapp = golemapp:start',
            'golemcli = golemcli:start',
        ]
    },
)

print_errors(ui_err, docker_err, task_collector_err)
