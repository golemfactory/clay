from buildbot.plugins import schedulers as bs


schedulers = [
    bs.AnyBranchScheduler(
        name='all',
        treeStableTimer=20,
        builderNames=[
            'buildpackage_macOS',
            'unittest_linux',
            'buildpackage_linux',
            'buildpackage_windows',
        ]),
    bs.ForceScheduler(
        name='force',
        builderNames=[
            'buildpackage_macOS',
            'unittest_macOS',
            'unittest_linux',
            'unittest_windows',
            'buildpackage_linux',
            'buildpackage_windows',
        ]),
]
