from buildbot.plugins import schedulers, util


branch_filter = util.ChangeFilter(branch_re=r'develop|b\d+\..+')


def pr_check(c):
    print("Check PR")
    print(c)
    return c.category == 'pull'


pr_filter = util.ChangeFilter(filter_fn=pr_check)

schedulers = [
    # Receiving updates and triggering the control jobs
    schedulers.AnyBranchScheduler(name='hook_pr',
                                  builderNames=['hook_pr'],
                                  change_filter=pr_filter),
    schedulers.AnyBranchScheduler(name='hook_push',
                                  builderNames=['hook_push'],
                                  change_filter=branch_filter),
    # Triggerable builds from control jobs
    schedulers.Triggerable(name="unittest-fast_control",
                           builderNames=['unittest-fast_control'],
                           properties={
                               'buildtype': 'test'
                           }),
    schedulers.Triggerable(name="unittest_control",
                           builderNames=['unittest_control'],
                           properties={
                               'buildtype': 'test'
                           }),
    schedulers.Triggerable(name="buildpackage_control",
                           builderNames=['buildpackage_control'],
                           properties={
                               'buildtype': 'build'
                           }),
    # The actual builds
    schedulers.Triggerable(name="linttest",
                           builderNames=['linttest']),
    schedulers.Triggerable(name="unittest-fast_macOS",
                           builderNames=['unittest-fast_macOS']),
    schedulers.Triggerable(name="unittest-fast_linux",
                           builderNames=['unittest-fast_linux']),
    schedulers.Triggerable(name="unittest-fast_windows",
                           builderNames=['unittest-fast_windows']),
    schedulers.Triggerable(name="unittest_macOS",
                           builderNames=['unittest_macOS']),
    schedulers.Triggerable(name="unittest_linux",
                           builderNames=['unittest_linux']),
    schedulers.Triggerable(name="unittest_windows",
                           builderNames=['unittest_windows']),
    schedulers.Triggerable(name="buildpackage_macOS",
                           builderNames=['buildpackage_macOS']),
    schedulers.Triggerable(name="buildpackage_linux",
                           builderNames=['buildpackage_linux']),
    schedulers.Triggerable(name="buildpackage_windows",
                           builderNames=['buildpackage_windows']),
    # Nighly uploads
    schedulers.Nightly(name='hook_nightly',
                       branch='develop',
                       builderNames=['hook_nightly'],
                       hour=4,
                       onlyIfChanged=True),
    # Be able to build all manually
    schedulers.ForceScheduler(
        name='force',
        builderNames=[
            'hook_pr',
            'hook_push',
            'unittest-fast_control',
            'unittest_control',
            'buildpackage_control',
            'linttest',
            'unittest-fast_macOS',
            'unittest-fast_linux',
            'unittest-fast_windows',
            'unittest_macOS',
            'unittest_linux',
            'unittest_windows',
            'buildpackage_macOS',
            'buildpackage_linux',
            'buildpackage_windows',
            'hook_nightly',
        ]),
]
