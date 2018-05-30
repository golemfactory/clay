from tests_dist.ProcTestFixture import ProcTestFixture

print('Integration test runner.py')

# Validate config
print('Validating config...')

# Start tests
print('Starting tests...')

class TestVersion(ProcTestFixture):
    def test_remote_version(self):
        print()
        print("DEBUG: Hello World")
        # TODO: Make sure LC_AL and LC_LANG are set
        args = [
            'ssh',
            'maaktweluit@192.168.178.172',
            'cd', '/home/maaktweluit/src/golem', ';',
            '.venv/bin/pytest', 'tests_dist/tests/test_version.py', '-s'
        ]
        
        # assert logs in right order
        exp_err = []
        exp_out = [
            '============================= test session starts ==============================', #  noqa
            'P: All expected out lines have been found'
        ]

        opts = {
            'cwd': None
        }
        exit_code, log_err, log_out, check_err_exp, check_out_exp = self.do_magic(opts, args, exp_err, exp_out) #  noqa

        assert check_out_exp == len(exp_out)
        print("P: All expected out lines have been found")

        assert check_err_exp == len(exp_err)
        print("P: All expected err lines have been found")

        print("DEBUG: OUT:" + str(len(log_out)))
        print(log_out)
        print("DEBUG: ERR:" + str(len(log_err)))
        print(log_err)
        # assert final test state
        assert exit_code == 0
        print("P: Exit code is 0")
        assert len(log_out) == 26 
        print("P: Test returns 26 lines")
        err_len = len(log_err)
        assert len(log_err) <= 5 
        if err_len > 0:
            print("W: Test does not expect stderr")
        else:
            print("P: Test stderr is empty")

print('Tests Completed!')

# Poll results
print('Monitoring results...')

print("OUT:")
# print(str(stdout))

print("ERR:")
# print(str(stderr))

# Print report
# print('Generating report...')
# print('Test case 1:')
# expected = bytes('GOLEM version: ' + version_check + '\n', 'utf-8')
# passed = stdout == expected
# print(str(expected))
# passed = 'always'
# print('assert(config_version == golemapp --version): ' + str(passed))
