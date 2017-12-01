import requests
from buildbot.plugins import steps, util

from .settings import buildbot_host


class StepsFactory(object):
    extra_requirements = [
        'git+https://github.com/pyinstaller/pyinstaller.git',
    ]

    # Basic Linux settings, override other platforms.
    platform = 'linux'
    venv_command = ['python3', '-m', 'venv']
    python_command = ['.venv/bin/python']
    pip_command = ['.venv/bin/pip']
    venv_bin_path = util.Interpolate('%(prop:builddir)s/build/.venv/bin')
    venv_path = util.Interpolate('%(prop:builddir)s/build/.venv')
    requirements_files = ['requirements.txt']
    pathsep = '/'
    golem_package = 'dist/golem.tar.gz'
    golem_package_extension = 'tar.gz'

    def build_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.create_binaries_step())
        factory.addStep(self.load_version_step())
        factory.addStep(self.file_upload_step())
        return factory

    @staticmethod
    def git_step():
        return steps.Git(
            repourl='https://github.com/maaktweluit/golem.git',
            mode='full', method='fresh', branch='mwu/bb-unit-test')

    def venv_step(self):
        return steps.ShellCommand(
            name='virtualenv',
            haltOnFailure=True,
            command=self.venv_command + ['.venv'])

    def requirements_step(self):
        gitpy_repo = 'git+https://github.com/gitpython-developers/GitPython'
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
                util.ShellArg(
                    logfile='install missing requirements',
                    haltOnFailure=True,
                    command=self.pip_command + ['install', gitpy_repo]),
            ],
            env={
                'LANG': 'en_US.UTF-8',  # required for readline
            })

    @staticmethod
    def taskcollector_step():
        return steps.ShellCommand(
            name='build taskcollector',
            haltOnFailure=True,
            command=['make', '-C', 'apps/rendering/resources/taskcollector'],
        )

    def create_binaries_step(self):
        return steps.ShellCommand(
            name='create binaries',
            haltOnFailure=True,
            command=self.python_command + ['setup.py', 'pyinstaller',
                                           '--package-path',
                                           self.golem_package],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'VIRTUAL_ENV': self.venv_path,
            })

    def file_upload_step(self):
        return steps.FileUpload(
            workersrc=util.Interpolate(self.golem_package),
            masterdest=util.Interpolate(
                '/var/build-artifacts/golem-%(prop:version)s-'
                '%(kw:platform)s.%(kw:ext)s',
                platform=self.platform,
                ext=self.golem_package_extension),
            url=util.Interpolate(
                '%(kw:buildbot_host)s/artifacts/golem-%(prop:version)s-'
                '%(kw:platform)s.%(kw:ext)s',
                buildbot_host=buildbot_host,
                platform=self.platform,
                ext=self.golem_package_extension),
            blocksize=640 * 1024,
            mode=0o644,
        )

    def load_version_step(self):
        return steps.ShellSequence(
            name='load current version',
            commands=[
                util.ShellArg(
                    logfile='generate version',
                    haltOnFailure=True,
                    command=self.python_command + [
                        r'Installer\Installer_Win\version.py']),
                steps.SetPropertyFromCommand(
                    command='cat .version.ini | '
                            'grep "version =" | grep -o "[^ =]*$"',
                    property='version')
            ])

    def test_factory(self, run_slow=False):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.daemon_start_step())
        factory.addStep(self.test_step(run_slow))
        factory.addStep(self.coverage_step(run_slow))
        factory.addStep(self.daemon_stop_step())
        return factory

    @staticmethod
    def daemon_start_step():
        return steps.ShellCommand(
            name='start hyperg',
            haltOnFailure=True,
            command=['scripts/test-daemon-start.sh'])

    def test_step(self, run_slow):
        install_req_cmd = self.pip_command + ['install', '-r',
                                              'requirements-test.txt']

        test_command = ['-m', 'pytest', '--cov=golem', '--durations=5', '-rxs']
        if run_slow:
            test_command += ['--runslow']

        # Since test-daemons are running commands should not halt on failure.
        return steps.ShellSequence(
            name='run tests',
            commands=[
                util.ShellArg(
                    logfile='install requirements',
                    flunkOnFailure=True,
                    command=install_req_cmd),
                # TODO: move to requirements itself?
                util.ShellArg(
                    logfile='install missing requirement',
                    flunkOnFailure=True,
                    command=self.pip_command + ['install', 'pyasn1==0.2.3',
                                                'codecov', 'pytest-cov']),
                util.ShellArg(
                    logfile='prepare for test',
                    flunkOnFailure=True,
                    command=self.python_command + ['setup.py', 'develop']),
                # TODO: add xml results
                # TODO 2: add run slow
                util.ShellArg(
                    logfile='run tests',
                    flunkOnFailure=True,
                    command=self.python_command + test_command)
            ])

    def coverage_step(self, run_slow):
        def is_slow(*_):
            return run_slow
        return steps.ShellCommand(
            name='handle coverage',
            flunkOnFailure=True,
            command=self.python_command + ['-m', 'codecov'],
            doStepIf=is_slow)

    @staticmethod
    def daemon_stop_step():
        return steps.ShellCommand(
            name='stop hyperg',
            haltOnFailure=True,
            command=['scripts/test-daemon-stop.sh'])

    def linttest_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        # TODO: add lint command
        return factory


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
    golem_package = r'Installer\Installer_Win\Golem_win_%(prop:version)s.exe'
    golem_package_extension = 'exe'

    def build_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.pywin32_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.create_binaries_step())
        factory.addStep(self.load_version_step())
        factory.addStep(self.create_installer_step())
        factory.addStep(self.file_upload_step())
        return factory

    def taskcollector_step(self):
        return steps.ShellCommand(
            name='build taskcollector',
            haltOnFailure=True,
            command=self.build_taskcollector_command,
            env={
                'PATH': r'${PATH};C:\Program Files (x86)'
                r'\Microsoft Visual Studio\2017\Community\MSBuild\15.0\Bin'
            }
        )

    def pywin32_step(self):
        return steps.ShellCommand(
            name='install pywin32',
            haltOnFailure=True,
            command=self.pip_command + [
                'install',
                r'C:\BuildResources\pywin32-221-cp36-cp36m-win_amd64.whl'
            ],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'VIRTUAL_ENV': self.venv_path,
            })

    @staticmethod
    def daemon_start_step():
        return steps.ShellCommand(
            name='start hyperg',
            haltOnFailure=True,
            command=['powershell.exe', r'scripts\test-daemon-start.ps1'])

    @staticmethod
    def daemon_stop_step():
        return steps.ShellCommand(
            name='stop hyperg',
            haltOnFailure=True,
            command=['powershell.exe', r'scripts\test-daemon-stop.ps1'])

    @staticmethod
    def create_installer_step():
        return steps.ShellCommand(
            name='run inno',
            haltOnFailure=True,
            command=['iscc', r'Installer\Installer_Win\install_script.iss'])


class LinuxStepsFactory(StepsFactory):
    pass


class MacOsStepsFactory(StepsFactory):
    platform = 'macOS'


class ControlStepFactory():
    @staticmethod
    def pr_control():

        @util.renderer
        def extract_pr_data(props):
            pr_number = props.getProperty('branch').split('/')[2]
            run_slow = True

            # config vars
            required_approvals = 1

            class ApprovalError(Exception):
                pass

            base_url = "https://api.github.com/" \
                "repos/maaktweluit/golem/pulls/{}/reviews"
            url = base_url.format(pr_number)

            try:
                # Github API requires user agent.
                req = requests.get(url, headers={'User-Agent': 'build-bot'})

                json_data = req.json()

                if "message" in json_data \
                        and json_data["message"].startswith("API rate"):

                    print("Raw reply:{}".format(json_data))
                    raise ApprovalError

                check_states = ["APPROVED", "CHANGES_REQUESTED"]
                review_states = [a for a in json_data if a["state"] in check_states]
                unique_reviews = {x['user']['login']: x for x in review_states}.values()

                result = [a for a in unique_reviews if a["state"] == "APPROVED"]
                approvals = len(result)
                run_slow = approvals >= required_approvals
            except(requests.HTTPError, requests.Timeout, ApprovalError) as e:
                print("Error calling github, run all tests. {}".format(url))

            return {'runslow': '--runslow' if run_slow else ''}

        def is_slow(step):
            return step.getProperty('runslow') != ''

        def is_fast(step):
            return step.getProperty('runslow') == ''

        factory = util.BuildFactory()
        # Check approvals
        factory.addStep(steps.SetProperties(properties=extract_pr_data))
        # Trigger fast if < 1
        factory.addStep(
            steps.Trigger(schedulerNames=['fast_test'],
                          waitForFinish=True,
                          doStepIf=is_fast,
                          # hideStepIf=is_slow,
                          haltOnFailure=True))
        # Trigger slow if >= 1
        factory.addStep(
            steps.Trigger(schedulerNames=['slow_test'],
                          waitForFinish=True,
                          doStepIf=is_slow,
                          # hideStepIf=is_fast,
                          haltOnFailure=True))
        # Trigger buildpackage if >= 1
        factory.addStep(
            steps.Trigger(schedulerNames=['build_package'],
                          waitForFinish=False,
                          doStepIf=is_slow,
                          # hideStepIf=is_fast,
                          haltOnFailure=True))
        return factory

    @staticmethod
    def branch_control():
        factory = util.BuildFactory()
        # Trigger slow
        factory.addStep(
            steps.Trigger(schedulerNames=['slow_test'],
                          waitForFinish=True,
                          haltOnFailure=True))
        # Trigger buildpackage
        factory.addStep(
            steps.Trigger(schedulerNames=['build_package'],
                          waitForFinish=False,
                          haltOnFailure=True))
        return factory

    @staticmethod
    def fast_test():
        factory = util.BuildFactory()
        factory.addStep(
            steps.SetProperty(value="test", property="buildtype"))
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'unittest_fast_macOS',
                    'unittest_fast_linux',
                    'unittest_fast_windows'],
                waitForFinish=True,
                haltOnFailure=True))
        return factory

    @staticmethod
    def slow_test():
        factory = util.BuildFactory()
        factory.addStep(
            steps.SetProperty(value="test", property="buildtype"))
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'unittest_macOS',
                    'unittest_linux',
                    'unittest_windows'],
                waitForFinish=True,
                haltOnFailure=True))
        return factory

    @staticmethod
    def build_package():
        factory = util.BuildFactory()
        factory.addStep(
            steps.SetProperty(value="build", property="buildtype"))
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'buildpackage_macOS',
                    'buildpackage_linux',
                    'buildpackage_windows'],
                waitForFinish=True,
                haltOnFailure=True))
        return factory

    @staticmethod
    def nightly_upload():
        factory = util.BuildFactory()

        # Get last nights SHA
        # Get last successfull develop package
        # Exit success when SHA's are the same

        # Get all packages from last successfull develop build
        # Upload to github nightly repository as release

        return factory


builders = [
    # controling builders
    util.BuilderConfig(name="pr_control", workernames=["control"],
                       factory=ControlStepFactory().pr_control()),
    util.BuilderConfig(name="branch_control", workernames=["control"],
                       factory=ControlStepFactory().branch_control()),
    util.BuilderConfig(name="fast_test", workernames=["control"],
                       factory=ControlStepFactory().fast_test()),
    util.BuilderConfig(name="slow_test", workernames=["control"],
                       factory=ControlStepFactory().slow_test()),
    util.BuilderConfig(name="build_package", workernames=["control"],
                       factory=ControlStepFactory().build_package()),
    util.BuilderConfig(name="nightly_upload", workernames=["control"],
                       factory=ControlStepFactory().nightly_upload()),
    # lint tests
    util.BuilderConfig(name="linttest", workernames=["linux"],
                       factory=LinuxStepsFactory().linttest_factory()),
    # fast unit tests
    util.BuilderConfig(name="unittest_fast_macOS", workernames=["macOS"],
                       factory=LinuxStepsFactory().test_factory(),
                       env={
                           'TRAVIS': 'TRUE',
                           # required for mkdir, ioreg, rm and cat
                           'PATH': ['/usr/sbin/', '/bin/', '${PATH}'],
                       }),
    util.BuilderConfig(name="unittest_fast_linux", workernames=["linux"],
                       factory=LinuxStepsFactory().test_factory()),
    util.BuilderConfig(name="unittest_fast_windows",
                       workernames=["windows_server_2016"],
                       factory=WindowsStepsFactory().test_factory(),
                       env={
                           'APPVEYOR': 'TRUE',
                           'PATH': ['${PATH}', 'C:\\BuildResources\\hyperg',
                                    'C:\\BuildResources\\geth-windows-amd64-1.7.2-1db4ecdc']
                       }),
    # slow unit tests
    util.BuilderConfig(name="unittest_macOS", workernames=["macOS"],
                       factory=LinuxStepsFactory().test_factory(True),
                       env={
                           'TRAVIS': 'TRUE',
                           # required for mkdir, ioreg, rm and cat
                           'PATH': ['/usr/sbin/', '/bin/', '${PATH}'],
                       }),
    util.BuilderConfig(name="unittest_linux", workernames=["linux"],
                       factory=LinuxStepsFactory().test_factory(True)),
    util.BuilderConfig(name="unittest_windows",
                       workernames=["windows_server_2016"],
                       factory=WindowsStepsFactory().test_factory(True),
                       env={
                           'APPVEYOR': 'TRUE',
                           'PATH': ['${PATH}', 'C:\\BuildResources\\hyperg',
                                    'C:\\BuildResources\\geth-windows-amd64-1.7.2-1db4ecdc']
                       }),
    # build package
    util.BuilderConfig(name="buildpackage_macOS", workernames=["macOS"],
                       factory=MacOsStepsFactory().build_factory()),
    util.BuilderConfig(name="buildpackage_linux", workernames=["linux"],
                       factory=LinuxStepsFactory().build_factory()),
    util.BuilderConfig(name="buildpackage_windows",
                       workernames=["windows_server_2016"],
                       factory=WindowsStepsFactory().build_factory()),
]
