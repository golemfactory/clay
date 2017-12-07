import requests
from twisted.internet import defer

# pylint: disable=E0401
from buildbot.plugins import steps, util
from buildbot.process import results
from buildbot.reporters import utils as reporters_utils
# pylint: enable=E0401

from .settings import buildbot_host


@defer.inlineCallbacks
def has_no_previous_success_check(step):
    # function taken from stackoverflow and adjusted for our use:
    # https://stackoverflow.com/questions/34284466/buildbot-how-do-i-skip-a-build-if-got-revision-is-the-same-as-the-last-run # noqa pylint: disable=C0301

    cur_build = step.build
    # never skip if this is a forced run
    if cur_build.getProperty("revision") is None \
            or cur_build.getProperty("revision") == "" \
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
        if prev_build['results'] == results.SUCCESS \
                and prev_build['properties']['revision'][0] \
                == cur_build.getProperty("revision"):
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
            repourl='https://github.com/maaktweluit/golem.git',
            mode='full', method='fresh', branch='mwu/bb-unit-test',
            doStepIf=has_no_previous_success)

    def venv_step(self):
        return steps.ShellCommand(
            name='virtualenv',
            haltOnFailure=True,
            command=self.venv_command + ['.venv'],
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
            },
            doStepIf=has_no_previous_success)

    @staticmethod
    def taskcollector_step():
        return steps.ShellCommand(
            name='build taskcollector',
            haltOnFailure=True,
            command=['make', '-C', 'apps/rendering/resources/taskcollector'],
            doStepIf=has_no_previous_success,
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
            },
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
            haltOnFailure=True,
            command=self.python_command + [self.version_script],
            doStepIf=has_no_previous_success)

    @staticmethod
    def load_version_step():
        return steps.SetPropertyFromCommand(
            command='cat .version.ini | '
                    'grep "version =" | grep -o "[^ =]*$"',
            property='version',
            doStepIf=has_no_previous_success)

    @staticmethod
    def daemon_start_step():
        return steps.ShellCommand(
            name='start hyperg',
            haltOnFailure=True,
            command=['scripts/test-daemon-start.sh'],
            doStepIf=has_no_previous_success)

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
            ],
            doStepIf=has_no_previous_success)

    def coverage_step(self, run_slow):
        def is_slow(*_):
            return run_slow
        return steps.ShellCommand(
            name='handle coverage',
            flunkOnFailure=True,
            command=self.python_command + ['-m', 'codecov'],
            doStepIf=has_no_previous_success and is_slow)

    @staticmethod
    def daemon_stop_step():
        return steps.ShellCommand(
            name='stop hyperg',
            haltOnFailure=True,
            command=['scripts/test-daemon-stop.sh'],
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
                        r'\Microsoft Visual Studio\2017\Community'
                        r'\MSBuild\15.0\Bin'
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
    def hook_pr():

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
                review_states = [
                    a for a in json_data if a["state"] in check_states]
                unique_reviews = {
                    x['user']['login']: x for x in review_states}.values()

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
            steps.Trigger(schedulerNames=['unittest-fast_control'],
                          waitForFinish=True,
                          doStepIf=is_fast,
                          # hideStepIf=is_slow,
                          haltOnFailure=True))
        # Trigger slow if >= 1
        factory.addStep(
            steps.Trigger(schedulerNames=['unittest_control'],
                          waitForFinish=True,
                          doStepIf=is_slow,
                          # hideStepIf=is_fast,
                          haltOnFailure=True))
        # Trigger buildpackage if >= 1
        factory.addStep(
            steps.Trigger(schedulerNames=['buildpackage_control'],
                          waitForFinish=False,
                          doStepIf=is_slow,
                          # hideStepIf=is_fast,
                          haltOnFailure=True))
        return factory

    @staticmethod
    def hook_push():
        factory = util.BuildFactory()
        # Trigger slow
        factory.addStep(
            steps.Trigger(schedulerNames=['unittest_control'],
                          waitForFinish=True,
                          haltOnFailure=True))
        # Trigger buildpackage
        factory.addStep(
            steps.Trigger(schedulerNames=['buildpackage_control'],
                          waitForFinish=False,
                          haltOnFailure=True))
        return factory

    @staticmethod
    def unittest_fast_control():
        factory = util.BuildFactory()
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'linttest',
                    'unittest-fast_macOS',
                    'unittest-fast_linux',
                    'unittest-fast_windows'],
                waitForFinish=True,
                haltOnFailure=True))
        return factory

    @staticmethod
    def unittest_control():
        factory = util.BuildFactory()
        factory.addStep(
            steps.Trigger(
                schedulerNames=[
                    'linttest',
                    'unittest_macOS',
                    'unittest_linux',
                    'unittest_windows'],
                waitForFinish=True,
                haltOnFailure=True))
        return factory

    @staticmethod
    def buildpackage_control():
        factory = util.BuildFactory()
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
    def hook_nightly():

        @util.renderer
        @defer.inlineCallbacks
        def get_last_nightly(step):

            @defer.inlineCallbacks
            def get_last_buildpackage_success(cur_build):

                # Get builderId and buildNumber to scan succesfull builds
                builder_id = yield cur_build.master.db.builders.findBuilderId(
                    'buildpackage_control', autoCreate=False)
                builder = yield cur_build.master.db.builds.getBuilds(
                    builderid=builder_id, complete=True)
                print('Build properties: {}'.format(builder))
                # TODO: Add check for only develop
                dict_build = {
                    'number': builder,
                    'builderid': builder_id
                }
                # print("Current build: {}".format(dict_build))
                prev_build = yield reporters_utils.getPreviousBuild(
                    cur_build.master,
                    dict_build)
                # this is the first build
                if prev_build is None:
                    print("No previous build to check success")
                    defer.returnValue(True)
                    return True
                while prev_build is not None:
                    if prev_build['results'] == results.SUCCESS:
                        yield reporters_utils.getDetailsForBuild(
                            cur_build.master,
                            prev_build,
                            wantProperties=True)
                        print("Found previous succes, skipping build")
                        defer.returnValue(
                            prev_build['properties']['revision'][0])
                        return False
                    prev_build = yield reporters_utils.getPreviousBuild(
                        cur_build.master,
                        prev_build)
                print("No previous success, run build")
                defer.returnValue(True)
                return True

            def is_uploaded_to_github(sha):

                base_url = "https://api.github.com/" \
                           "repos/maaktweluit/golem/releases"

                try:
                    # Github API requires user agent.
                    req = requests.get(
                        base_url, headers={'User-Agent': 'build-bot'})

                    if req.text.contains("API rate"):
                        print("Raw reply:{}".format(req.text))
                        raise Exception("Cant get latest release from github")

                    # Check if SHA to upload is on the return data
                    return req.text.contains(sha)
                except(requests.HTTPError, requests.Timeout) as e:
                    print("Error calling github, run all tests."
                          " {} - {}".format(base_url, e))

                return False

            print("Nightly hook")
            master_result = yield get_last_buildpackage_success(step.build)
            print("Master result: {}".format(master_result))
            github_result = is_uploaded_to_github(master_result)
            print("Githuib result: {}".format(github_result))
            defer.returnValue({
                'same_as_github': github_result,
                'last_nightly_build': master_result
            })

        def is_not_same(step):
            return not step.getProperty('same_as_github')

        factory = util.BuildFactory()

        # Get last nights SHA from github releases
        # Get last successfull develop package from artefact dir
        # Exit success when SHA's are the same
        factory.addStep(steps.SetProperties(properties=get_last_nightly))

        # Get all packages from last successfull develop build
        # factory.addStep(download all 3 packages, doStepIf=is_not_same)
        # Upload to github nightly repository as release
        # factory.addStep(upload all 3 packages, doStepIf=is_not_same)

        return factory


build_lock = util.WorkerLock("worker_builds",
                             maxCount=1).access('counting')

control_workers = [
    "control_01",
    "control_02",
    "control_03",
    "control_04",
]

builders = [
    # controling builders
    util.BuilderConfig(name="hook_pr", workernames=control_workers,
                       factory=ControlStepFactory().hook_pr()),
    util.BuilderConfig(name="hook_push", workernames=control_workers,
                       factory=ControlStepFactory().hook_push()),
    util.BuilderConfig(name="unittest-fast_control",
                       workernames=control_workers,
                       factory=ControlStepFactory().unittest_fast_control()),
    util.BuilderConfig(name="unittest_control", workernames=control_workers,
                       factory=ControlStepFactory().unittest_control()),
    util.BuilderConfig(name="buildpackage_control", workernames=control_workers,
                       factory=ControlStepFactory().buildpackage_control()),
    util.BuilderConfig(name="hook_nightly", workernames=control_workers,
                       factory=ControlStepFactory().hook_nightly(),
                       locks=[build_lock]),
    # lint tests
    util.BuilderConfig(name="linttest", workernames=["linux"],
                       factory=LinuxStepsFactory().linttest_factory(),
                       locks=[build_lock]),
    # fast unit tests
    util.BuilderConfig(name="unittest-fast_macOS", workernames=["macOS"],
                       factory=LinuxStepsFactory().test_factory(),
                       env={
                           'TRAVIS': 'TRUE',
                           # required for mkdir, ioreg, rm and cat
                           'PATH': ['/usr/sbin/', '/bin/', '${PATH}'],
                       },
                       locks=[build_lock]),
    util.BuilderConfig(name="unittest-fast_linux", workernames=["linux"],
                       factory=LinuxStepsFactory().test_factory(),
                       locks=[build_lock]),
    util.BuilderConfig(name="unittest-fast_windows",
                       workernames=["windows_server_2016"],
                       factory=WindowsStepsFactory().test_factory(),
                       env={
                           'APPVEYOR': 'TRUE',
                           'PATH': ['${PATH}', 'C:\\BuildResources\\hyperg',
                                    r'C:\BuildResources'
                                    r'\geth-windows-amd64-1.7.2-1db4ecdc']
                       },
                       locks=[build_lock]),
    # slow unit tests
    util.BuilderConfig(name="unittest_macOS", workernames=["macOS"],
                       factory=LinuxStepsFactory().test_factory(True),
                       env={
                           'TRAVIS': 'TRUE',
                           # required for mkdir, ioreg, rm and cat
                           'PATH': ['/usr/sbin/', '/bin/', '${PATH}'],
                       },
                       locks=[build_lock]),
    util.BuilderConfig(name="unittest_linux", workernames=["linux"],
                       factory=LinuxStepsFactory().test_factory(True)),
    util.BuilderConfig(name="unittest_windows",
                       workernames=["windows_server_2016"],
                       factory=WindowsStepsFactory().test_factory(True),
                       env={
                           'APPVEYOR': 'TRUE',
                           'PATH': ['${PATH}', 'C:\\BuildResources\\hyperg',
                                    r'C:\BuildResources'
                                    r'\geth-windows-amd64-1.7.2-1db4ecdc']
                       },
                       locks=[build_lock]),
    # build package
    util.BuilderConfig(name="buildpackage_macOS", workernames=["macOS"],
                       factory=MacOsStepsFactory().build_factory(),
                       locks=[build_lock]),
    util.BuilderConfig(name="buildpackage_linux", workernames=["linux"],
                       factory=LinuxStepsFactory().build_factory(),
                       locks=[build_lock]),
    util.BuilderConfig(name="buildpackage_windows",
                       workernames=["windows_server_2016"],
                       factory=WindowsStepsFactory().build_factory(),
                       locks=[build_lock]),
]
