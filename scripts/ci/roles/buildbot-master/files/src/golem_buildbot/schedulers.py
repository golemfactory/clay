from buildbot.plugins import schedulers, util


branch_filter = util.ChangeFilter(branch_re=r'develop|b\d+\..+')


def pr_check(c):
    print("Check PR")
    print(c)
    return c.category == 'pull'


pr_filter = util.ChangeFilter(filter_fn=pr_check)

schedulers = [
    # Receiving updates and triggering the control jobs
    schedulers.AnyBranchScheduler(name='pr_control',
                                  builderNames=['pr_control'],
                                  change_filter=pr_filter),
    schedulers.AnyBranchScheduler(name='branch_control',
                                  builderNames=['branch_control'],
                                  change_filter=branch_filter),
    # Triggerable builds from control jobs
    schedulers.Triggerable(name="fast_test",
                           builderNames=['fast_test']),
    schedulers.Triggerable(name="slow_test",
                           builderNames=['slow_test']),
    schedulers.Triggerable(name="build_package",
                           builderNames=['build_package']),
    schedulers.Triggerable(name="linttest",
                           builderNames=['linttest']),
    schedulers.Triggerable(name="unittest_fast_macOS",
                           builderNames=['unittest_fast_macOS']),
    schedulers.Triggerable(name="unittest_fast_linux",
                           builderNames=['unittest_fast_linux']),
    schedulers.Triggerable(name="unittest_fast_windows",
                           builderNames=['unittest_fast_windows']),
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
    schedulers.Nightly(name='nightly_upload',
                       branch='develop',
                       builderNames=['nightly_upload'],
                       hour=4,
                       onlyIfChanged=True),
    # Be able to build all manually
    schedulers.ForceScheduler(
        name='force',
        builderNames=[
            'pr_control',
            'branch_control',
            'fast_test',
            'slow_test',
            'build_package',
            'linttest',
            'unittest_fast_macOS',
            'unittest_fast_linux',
            'unittest_fast_windows',
            'unittest_macOS',
            'unittest_linux',
            'unittest_windows',
            'buildpackage_macOS',
            'buildpackage_linux',
            'buildpackage_windows',
            'nightly_upload',
        ]),
]
