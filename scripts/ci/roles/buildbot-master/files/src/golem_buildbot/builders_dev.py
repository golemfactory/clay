from twisted.internet import defer

# pylint: disable=E0401
from buildbot.plugins import steps, util
from buildbot.process import results
from buildbot.reporters import utils as reporters_utils
# pylint: enable=E0401

from .settings import buildbot_host, github_slug
from .builders_util import extract_rev


@defer.inlineCallbacks
def has_no_previous_success_check(step):
    # function taken from stackoverflow and adjusted for our use:
    # https://stackoverflow.com/questions/34284466/buildbot-how-do-i-skip-a-build-if-got-revision-is-the-same-as-the-last-run # noqa pylint: disable=C0301

    cur_build = step.build
    cur_rev = cur_build.getProperty("revision")
    cur_slow = cur_build.getProperty("runslow")
    if cur_rev is None or cur_rev == "":
        cur_rev = cur_build.getProperty("got_revision")
    # never skip if this is a forced run
    if cur_rev is None or cur_rev == "" \
            or cur_build.getProperty("scheduler") == "force":
        print("No check for succes on force build")
        defer.returnValue(True)
        return True

    # Get builderId and buildNumber to scan succesfull builds
    # print("Properties build: {}".format(cur_build.getProperties()))
    builder_id = yield cur_build.master.db.builders.findBuilderId(
        cur_build.getProperty('buildername'), autoCreate=False)
    dict_build = {
        'number': cur_build.number,
        'builderid': builder_id
    }
    # print("Current build: {}".format(dict_build))
    prev_build = yield reporters_utils.getPreviousBuild(step.build.master,
                                                        dict_build)
    # this is the first build
    if prev_build is None:
        print("No previous build to check success")
        defer.returnValue(True)
        return True
    while prev_build is not None:
        yield reporters_utils.getDetailsForBuild(step.build.master,
                                                 prev_build,
                                                 wantProperties=True)
        # print("Previous build: {}".format(dict_build))
        prev_rev = extract_rev(prev_build['properties'])
        prev_slow = prev_build['properties']['runslow'][0] \
            if 'runslow' in prev_build['properties'] else None
        # print("Properties prev build: {}".format(prev_build['properties']))

        if prev_build['results'] == results.SUCCESS \
                and prev_rev == cur_rev \
                and prev_slow == cur_slow:
            print("Found previous succes, skipping build")
            defer.returnValue(False)
            return False
        prev_build = yield reporters_utils.getPreviousBuild(step.build.master,
                                                            prev_build)
    print("No previous success, run build")
    defer.returnValue(True)
    return True


@defer.inlineCallbacks
def has_no_previous_success(step):
    last_success = step.build.getProperty('checked_success')
    print("Checked if last step was success: {}".format(last_success))
    if last_success is None:
        last_success = yield has_no_previous_success_check(step)
        print("Storing result of first success check: {}".format(last_success))
        step.build.setProperty('checked_success', last_success)
    defer.returnValue(last_success)
    return last_success


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
    version_script = 'Installer/Installer_Win/version.py'

    def build_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.create_binaries_step())
        factory.addStep(self.create_version_step())
        factory.addStep(self.load_version_step())
        factory.addStep(self.file_upload_step())
        return factory

    def test_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.daemon_start_step())
        factory.addSteps(self.test_step())
        factory.addStep(self.coverage_step())
        factory.addStep(self.daemon_stop_step())
        return factory

    def linttest_factory(self):
        self.requirements_files += ['requirements-lint.txt']
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.lint_step())
        return factory

    @staticmethod
    def git_step():
        return steps.Git(
            repourl='https://github.com/{}.git'.format(github_slug),
            mode='full', method='fresh', branch='develop',
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    def venv_step(self):
        return steps.ShellCommand(
            name='virtualenv',
            command=self.venv_command + ['.venv'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

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
                    command=self.pip_command + ['install', 'wheel'],
                    haltOnFailure=True),
                util.ShellArg(
                    logfile='upgrade pip',
                    command=self.pip_command + ['install', '--upgrade', 'pip'],
                    haltOnFailure=True),
                util.ShellArg(
                    logfile='install requirements',
                    command=install_req_cmd,
                    haltOnFailure=True),
                util.ShellArg(
                    logfile='uninstall enum34',
                    command=self.pip_command + ['uninstall', '-y', 'enum34'],
                    haltOnFailure=True),
                util.ShellArg(
                    logfile='install missing requirements',
                    command=self.pip_command + ['install', '--upgrade',
                                                gitpy_repo],
                    haltOnFailure=True),
                util.ShellArg(
                    logfile='setup.py develop',
                    command=self.python_command + ['setup.py', 'develop'],
                    haltOnFailure=True),
            ],
            env={
                'LANG': 'en_US.UTF-8',  # required for readline
            },
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    @staticmethod
    def taskcollector_step():
        return steps.ShellCommand(
            name='build taskcollector',
            command=['make', '-C', 'apps/rendering/resources/taskcollector'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success,
        )

    def create_binaries_step(self):
        return steps.ShellCommand(
            name='create binaries',
            command=self.python_command + ['setup.py', 'pyinstaller',
                                           '--package-path',
                                           self.golem_package],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'VIRTUAL_ENV': self.venv_path,
            },
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    def file_upload_step(self):
        return steps.FileUpload(
            workersrc=util.Interpolate(self.golem_package),
            masterdest=util.Interpolate(
                '/var/build-artifacts/%(prop:branch)s'
                '/golem-%(prop:version)s-%(kw:platform)s.%(kw:ext)s',
                platform=self.platform,
                ext=self.golem_package_extension),
            url=util.Interpolate(
                '%(kw:buildbot_host)s/artifacts/%(prop:branch)s'
                '/golem-%(prop:version)s-%(kw:platform)s.%(kw:ext)s',
                buildbot_host=buildbot_host,
                platform=self.platform,
                ext=self.golem_package_extension),
            blocksize=640 * 1024,
            mode=0o644,
            doStepIf=has_no_previous_success,
        )

    def create_version_step(self):
        return steps.ShellCommand(
            name='load current version',
            command=self.python_command + [self.version_script],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    @staticmethod
    def load_version_step():
        return steps.SetPropertyFromCommand(
            command='cat .version.ini | '
                    'grep "version =" | grep -o "[^ =]*$"',
            property='version',
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    @staticmethod
    def daemon_start_step():
        return steps.ShellCommand(
            name='start hyperg',
            command=['scripts/test-daemon-start.sh'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    def test_step(self):
        install_req_cmd = self.pip_command + ['install', '-r',
                                              'requirements-test.txt']

        test_command = ['-m', 'pytest', '--cov=golem', '--durations=5', '-rxs']

        test_slow_command = test_command + ['--runslow']

        @defer.inlineCallbacks
        def is_fast(step):
            has_no_success = yield has_no_previous_success(step)
            if not has_no_success:
                defer.returnValue(False)
            defer.returnValue(step.build.getProperty('runslow') == '')

        @defer.inlineCallbacks
        def is_slow(step):
            has_no_success = yield has_no_previous_success(step)
            if not has_no_success:
                defer.returnValue(False)
            defer.returnValue(step.build.getProperty('runslow') != '')

        # Since test-daemons are running commands should not halt on failure.
        return [
            steps.ShellSequence(
                name='run tests',
                commands=[
                    util.ShellArg(
                        logfile='install requirements',
                        command=install_req_cmd,
                        flunkOnFailure=True),
                    # TODO: move to requirements itself?
                    util.ShellArg(
                        logfile='install missing requirement',
                        command=self.pip_command + ['install', 'pyasn1==0.2.3',
                                                    'codecov', 'pytest-cov'],
                        flunkOnFailure=True),
                    # TODO: add xml results
                    # TODO 2: add run slow
                    util.ShellArg(
                        logfile='run tests',
                        command=self.python_command + test_command,
                        flunkOnFailure=True),
                ],
                env={
                    'LANG': 'en_US.UTF-8',  # required for test with 'click'
                },
                flunkOnFailure=True,
                doStepIf=is_fast),
            steps.ShellSequence(
                name='run slow tests',
                commands=[
                    util.ShellArg(
                        logfile='install requirements',
                        command=install_req_cmd,
                        flunkOnFailure=True),
                    # TODO: move to requirements itself?
                    util.ShellArg(
                        logfile='install missing requirement',
                        command=self.pip_command + ['install', 'pyasn1==0.2.3',
                                                    'codecov', 'pytest-cov'],
                        flunkOnFailure=True),
                    # TODO: add xml results
                    # TODO 2: add run slow
                    util.ShellArg(
                        logfile='run tests',
                        command=self.python_command + test_slow_command,
                        flunkOnFailure=True),
                ],
                env={
                    'LANG': 'en_US.UTF-8',  # required for test with 'click'
                },
                flunkOnFailure=True,
                doStepIf=is_slow),
            ]

    def coverage_step(self):

        @defer.inlineCallbacks
        def is_slow(step):
            prev_success = yield has_no_previous_success(step)
            run_slow = step.getProperty('runslow') != ''
            print("Check coverage is_slow: {} and {}".format(prev_success,
                                                             run_slow))
            defer.returnValue(prev_success and run_slow)

        return steps.ShellCommand(
            name='handle coverage',
            command=self.python_command + ['-m', 'codecov'],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'CODECOV_TOKEN': util.Interpolate(
                    '%(secret:codecov_api_token)s'),
                'CODECOV_SLUG': github_slug
            },
            flunkOnFailure=True,
            doStepIf=is_slow,
        )

    @staticmethod
    def daemon_stop_step():
        return steps.ShellCommand(
            name='stop hyperg',
            command=['scripts/test-daemon-stop.sh'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    def lint_step(self):
        return steps.ShellSequence(
            name='run tests',
            commands=[
                util.ShellArg(
                    logfile='update to develop',
                    haltOnFailure=True,
                    command=['git', 'merge', 'origin/develop']),
                util.ShellArg(
                    logfile='run lint.sh',
                    haltOnFailure=True,
                    command=['./lint.sh', 'origin/develop']),
            ],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
            },
            doStepIf=has_no_previous_success)


class WindowsStepsFactory(StepsFactory):
    platform = 'windows'
    venv_command = ['py', '-3', '-m', 'venv']
    python_command = [r'.venv\Scripts\python.exe']
    pip_command = [r'.venv\Scripts\pip.exe']
    venv_bin_path = util.Interpolate(r'%(prop:builddir)s\build\.venv\Scripts')
    venv_path = util.Interpolate(r'%(prop:builddir)s\build\.venv')
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
    version_script = r'Installer\Installer_Win\version.py'

    def build_factory(self):
        factory = util.BuildFactory()
        factory.addStep(self.git_step())
        factory.addStep(self.venv_step())
        factory.addStep(self.pywin32_step())
        factory.addStep(self.requirements_step())
        factory.addStep(self.taskcollector_step())
        factory.addStep(self.create_binaries_step())
        factory.addStep(self.create_version_step())
        factory.addStep(self.load_version_step())
        factory.addStep(self.create_installer_step())
        factory.addStep(self.file_upload_step())
        return factory

    def taskcollector_step(self):
        return steps.ShellCommand(
            name='build taskcollector',
            command=self.build_taskcollector_command,
            env={
                'PATH': r'${PATH};C:\Program Files (x86)'
                        r'\Microsoft Visual Studio\2017\Community'
                        r'\MSBuild\15.0\Bin'
            },
            haltOnFailure=True,
            doStepIf=has_no_previous_success
        )

    def pywin32_step(self):
        return steps.ShellCommand(
            name='install pywin32',
            command=self.pip_command + [
                'install',
                r'C:\BuildResources\pywin32-221-cp36-cp36m-win_amd64.whl'
            ],
            env={
                'PATH': [self.venv_bin_path, '${PATH}'],
                'VIRTUAL_ENV': self.venv_path,
            },
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    @staticmethod
    def daemon_start_step():
        return steps.ShellCommand(
            name='start hyperg',
            command=['powershell.exe', r'scripts\test-daemon-start.ps1'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    @staticmethod
    def daemon_stop_step():
        return steps.ShellCommand(
            name='stop hyperg',
            command=['powershell.exe', r'scripts\test-daemon-stop.ps1'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)

    @staticmethod
    def create_installer_step():
        return steps.ShellCommand(
            name='run inno',
            command=['iscc', r'Installer\Installer_Win\install_script.iss'],
            haltOnFailure=True,
            doStepIf=has_no_previous_success)


class LinuxStepsFactory(StepsFactory):
    pass


class MacOsStepsFactory(StepsFactory):
    platform = 'macOS'
