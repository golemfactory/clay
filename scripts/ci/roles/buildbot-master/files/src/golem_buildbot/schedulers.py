import re

# pylint: disable=E0401
from buildbot.plugins import schedulers, util
# pylint: enable=E0401


def branch_check(c):
    print("Branch check {}".format(c))
    if c.category == 'pull':
        return False

    if c.branch == 'develop' or re.match('b[0-9].*', c.branch):
        return True

    return False


def pr_check(c):
    print("Pull check {}".format(c))
    return c.category == 'pull'


branch_filter = util.ChangeFilter(filter_fn=branch_check)
pr_filter = util.ChangeFilter(filter_fn=pr_check)

schedulers = [
    # Receiving updates and triggering the control jobs
    schedulers.AnyBranchScheduler(name='hook_pr',
                                  builderNames=['hook_pr'],
                                  change_filter=pr_filter),
    schedulers.AnyBranchScheduler(name='hook_push',
                                  builderNames=['hook_push'],
                                  change_filter=branch_filter),
    schedulers.Nightly(name='hook_nightly',
                       branch='develop',
                       builderNames=['hook_nightly'],
                       hour=4,
                       onlyIfChanged=True),
    # Triggerable builds from control jobs
    schedulers.Triggerable(name="control_test",
                           builderNames=['control_test']),
    schedulers.Triggerable(name="control_build",
                           builderNames=['control_build']),
    # The actual builds
    schedulers.Triggerable(name="buildpackage_macOS",
                           builderNames=['buildpackage_macOS']),
    schedulers.Triggerable(name="buildpackage_linux",
                           builderNames=['buildpackage_linux']),
    schedulers.Triggerable(name="buildpackage_windows",
                           builderNames=['buildpackage_windows']),
    schedulers.Triggerable(name="linttest",
                           builderNames=['linttest']),
    schedulers.Triggerable(name="unittest_macOS",
                           builderNames=['unittest_macOS']),
    schedulers.Triggerable(name="unittest_linux",
                           builderNames=['unittest_linux']),
    schedulers.Triggerable(name="unittest_windows",
                           builderNames=['unittest_windows']),
    # Be able to build all manually
    schedulers.ForceScheduler(
        name='force',
        builderNames=[
            'hook_pr',
            'hook_push',
            'hook_nightly',
            'control_test',
            'control_build',
            'buildpackage_macOS',
            'buildpackage_linux',
            'buildpackage_windows',
            'linttest',
            'unittest_macOS',
            'unittest_linux',
            'unittest_windows',
        ]),
]
