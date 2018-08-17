from tests_dist.lib import TestSession

print('Integration test runner.py')

# Validate config
print('Validating config...')

# Start tests
print('Starting tests...')

# TODO: Make sure LC_AL and LC_LANG are set

class TestVersion:
    def test_remote_version(self):
        print()
        print("DEBUG: Hello World")

        test_1 = TestSession(
            [
                #    'ssh',
                #    'maaktweluit@192.168.178.172',
                #    'cd', '/home/maaktweluit/src/golem', ';',
                '.venv/bin/pytest', 'tests_dist/tests/test_version.py', '-s'
            ],
            {
                'cwd': None
            },       
                # assert logs in right order
            [],
            [
                '============================= test session starts ==============================', #  noqa
                'P: All expected out lines have been found'
            ]
        )

        test_2 = TestSession(
            [
                #    'ssh',
                #    'maaktweluit@192.168.178.172',
                #    'cd', '/home/maaktweluit/src/golem', ';',
                '.venv/bin/pytest', 'tests_dist/tests/test_version.py', '-s'
            ],
            {
                'cwd': None
            },       
                # assert logs in right order
            [],
            [
                '============================= test session starts ==============================', #  noqa
                'P: All expected out lines have been found'
            ]
        )

        exit_1 = None
        exit_2 = None
        while True:
            if exit_1 is None:
                exit_1 = test_1.tick()
            if exit_2 is None:
                exit_2 = test_2.tick()
            # are we there yet?
            if exit_1 is not None and exit_2 is not None:
                break

        test_1.report()
        test_2.report()

print('Tests Completed!')

# Poll results
print('Monitoring results...')
