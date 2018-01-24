# pylint: disable=E0401
from buildbot.plugins import util
# pylint: enable=E0401

from .builders_dev import LinuxStepsFactory, WindowsStepsFactory, \
    MacOsStepsFactory
from .builders_control import ControlStepFactory

from .workers import control_workers, macos_workers, linux_workers, \
    windows_workers

builders = [
    # controling builders
    util.BuilderConfig(name="hook_pr", workernames=control_workers,
                       factory=ControlStepFactory().hook_pr()),
    util.BuilderConfig(name="hook_push", workernames=control_workers,
                       factory=ControlStepFactory().hook_push()),
    util.BuilderConfig(name="control_test", workernames=control_workers,
                       factory=ControlStepFactory().control_test()),
    util.BuilderConfig(name="control_build", workernames=control_workers,
                       factory=ControlStepFactory().control_build()),
    util.BuilderConfig(name="hook_nightly", workernames=control_workers,
                       factory=ControlStepFactory().hook_nightly()),
    # lint tests
    util.BuilderConfig(name="linttest", workernames=linux_workers,
                       factory=LinuxStepsFactory().linttest_factory()),
    # slow unit tests
    util.BuilderConfig(name="unittest_macOS", workernames=macos_workers,
                       factory=LinuxStepsFactory().test_factory(),
                       env={
                           'TRAVIS': 'TRUE',
                           # required for mkdir, ioreg, rm and cat
                           'PATH': ['/usr/sbin/', '/bin/', '${PATH}'],
                       }),
    util.BuilderConfig(name="unittest_linux", workernames=linux_workers,
                       factory=LinuxStepsFactory().test_factory()),
    util.BuilderConfig(name="unittest_windows",
                       workernames=windows_workers,
                       factory=WindowsStepsFactory().test_factory(),
                       env={
                           'APPVEYOR': 'TRUE',
                           'PATH': ['${PATH}', 'C:\\BuildResources\\hyperg',
                                    r'C:\BuildResources'
                                    r'\geth-windows-amd64-1.7.2-1db4ecdc']
                       }),
    # build package
    util.BuilderConfig(name="buildpackage_macOS", workernames=macos_workers,
                       factory=MacOsStepsFactory().build_factory(),
                       env={
                           'TRAVIS': 'TRUE',
                           # required for mkdir, ioreg, rm and cat
                           'PATH': ['/usr/sbin/', '/bin/', '${PATH}'],
                       }),
    util.BuilderConfig(name="buildpackage_linux", workernames=linux_workers,
                       factory=LinuxStepsFactory().build_factory()),
    util.BuilderConfig(name="buildpackage_windows",
                       workernames=windows_workers,
                       factory=WindowsStepsFactory().build_factory(),
                       env={
                           'APPVEYOR': 'TRUE',
                       }),
]
