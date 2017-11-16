from buildbot.plugins import steps, util

from .settings import buildbot_host


class StepsFactory(object):
    extra_requirements = [
        'git+https://github.com/pyinstaller/pyinstaller.git',
    ]

    def build_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.create_binaries_step())
        factory.addStep(self.file_upload_step())
        return factory

    def git_step(self):
        return steps.Git(
            repourl='https://github.com/golemfactory/golem.git',
            mode='full', method='fresh')

    def venv_step(self):
        return steps.ShellCommand(
            name='virtualenv',
            haltOnFailure=True,
            command=self.venv_command + ['.venv'])

    def requirements_step(self):
        install_req_cmd = self.pip_command + ['install']
        for rf in self.requirements_files:
            install_req_cmd.append('-r')
            install_req_cmd.append(rf)
        install_req_cmd.extend(self.extra_requirements)

        return steps.ShellSequence(
            name='pip',
            commands=[
                util.ShellArg(
                    logfile='install wheel',
                    haltOnFailure=True,
                    command=self.pip_command + ['install', 'wheel']),
                util.ShellArg(
                    logfile='upgrade pip',
                    haltOnFailure=True,
                    command=self.pip_command + ['install', '--upgrade', 'pip']),
                util.ShellArg(
                    logfile='install requirements',
                    haltOnFailure=True,
                    command=install_req_cmd),
                util.ShellArg(
                    logfile='uninstall enum34',
                    haltOnFailure=True,
                    command=self.pip_command + ['uninstall', '-y', 'enum34']),
            ],
            env={
                'LANG': 'en_US.UTF-8',  # required for readline
            })

    def create_binaries_step(self):
        return steps.ShellCommand(
            name='create binaries',
            haltOnFailure=True,
            command=self.python_command + ['setup.py', 'pyinstaller',
                     '--package-path', self.golem_package],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'VIRTUAL_ENV': self.venv_path,
            })

    def file_upload_step(self):
        return steps.FileUpload(
            workersrc=self.golem_package,
            masterdest=util.Interpolate(
                '/var/build-artifacts/golem-%(prop:got_revision)s-%(kw:platform)s.%(kw:ext)s',
                platform=self.platform,
                ext=self.golem_package_extension),
            url=util.Interpolate(
                '%(kw:buildbot_host)s/artifacts/golem-%(prop:got_revision)s-%(kw:platform)s.%(kw:ext)s',
                buildbot_host=buildbot_host,
                platform=self.platform,
                ext=self.golem_package_extension),
            blocksize=640 * 1024,
            mode=0o644,
        )

    def test_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.test_step())
        return factory

    def test_step(self):
        install_req_cmd = self.pip_command + ['install', '-r',
                                              'requirements-test.txt']

        return steps.ShellSequence(
            name='run tests',
            commands=[
                util.ShellArg(
                    logfile='install requirements',
                    haltOnFailure=True,
                    command=install_req_cmd),
                # TODO: move to requirements itself?
                util.ShellArg(
                    logfile='install missing requirement',
                    haltOnFailure=True,
                    command=self.pip_command + ['install', 'pyasn1==0.2.3',
                                                'codecov', 'pytest-cov']),
                util.ShellArg(
                    logfile='prepare for test',
                    haltOnFailure=True,
                    command=self.python_command + ['setup.py', 'develop']),
                util.ShellArg(
                    logfile='start hyperg',
                    haltOnFailure=True,
                    command=['scripts/test-daemon-start.sh']),
                # TODO: add xml results
                # TODO 2: add run slow
                util.ShellArg(
                    logfile='run tests',
                    warnOnFailure=True,
                    command=self.python_command + ['-m', 'pytest',
                                                   '--cov=golem',
                                                   '--durations=5',
                                                   '-rxs', '--runslow']),
                util.ShellArg(
                    logfile='handle coverage',
                    warnOnFailure=True,
                    command=self.python_command + ['-m', 'codecov']),
                util.ShellArg(
                    logfile='stop hyperg',
                    haltOnFailure=True,
                    command=['scripts/test-daemon-stop.sh']),
            ])


class WindowsStepsFactory(StepsFactory):
    platform = 'windows'
    venv_command = ['py', '-3', '-m', 'venv']
    python_command = ['.venv\Scripts\python.exe']
    pip_command = ['.venv\Scripts\pip.exe']
    venv_bin_path = util.Interpolate('%(prop:builddir)s\\build\\.venv\\Scripts')
    venv_path = util.Interpolate('%(prop:builddir)s\\build\\.venv')
    requirements_files = ['requirements.txt', 'requirements-win.txt']
    build_taskcollector_command = [
        'msbuild',
        r'apps\rendering\resources\taskcollector\taskcollector.sln',
        r'/p:Configuration=Release',
        r'/p:Platform=x64',
    ]
    extra_requirements = StepsFactory.extra_requirements + ['pyethash==0.1.23']
    pathsep = '\\'
    golem_package = 'dist\\golem.zip'
    golem_package_extension = 'zip'

    def build_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.pywin32_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.create_binaries_step())
        factory.addStep(self.file_upload_step())
        return factory

    def taskcollector_step(self):
        return steps.ShellCommand(
            name='build taskcollector',
            haltOnFailure=True,
            command=self.build_taskcollector_command,
            env={
                'PATH': r'${PATH};C:\Program Files (x86)\Microsoft Visual Studio\2017\Community\MSBuild\15.0\Bin'
            }
        )

    def pywin32_step(self):
        return steps.ShellCommand(
            name='install pywin32',
            haltOnFailure=True,
            command=self.pip_command + [
                'install', ' C:\\BuildResources\\pywin32-221-cp36-cp36m-win_amd64.whl'
            ],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'VIRTUAL_ENV': self.venv_path,
            })


class PosixStepsFactory(StepsFactory):
    venv_command = ['python3', '-m', 'venv']
    python_command = ['.venv/bin/python']
    pip_command = ['.venv/bin/pip']
    venv_bin_path = util.Interpolate('%(prop:builddir)s/build/.venv/bin')
    venv_path = util.Interpolate('%(prop:builddir)s/build/.venv')
    requirements_files = ['requirements.txt']
    pathsep = '/'
    golem_package = 'dist/golem.tar.gz'
    golem_package_extension = 'tar.gz'


class LinuxStepsFactory(PosixStepsFactory):
    platform = 'linux'


class MacOsStepsFactory(PosixStepsFactory):
    platform = 'macOS'


builders = [
    util.BuilderConfig(name="buildpackage_macOS",
        workernames=["macOS"],
        factory=MacOsStepsFactory().build_factory()),
    util.BuilderConfig(name="unittest_linux",
        workernames=["linux"],
        factory=LinuxStepsFactory().test_factory()),
    util.BuilderConfig(name="buildpackage_linux",
        workernames=["linux"],
        factory=LinuxStepsFactory().build_factory()),
    util.BuilderConfig(name="buildpackage_windows",
        workernames=["windows_server_2016"],
        factory=WindowsStepsFactory().build_factory()),
]
