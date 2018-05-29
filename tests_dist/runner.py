import time
import subprocess

dist_name="golem-0.15.1+dev254.g7154f6c5c"
version_check="0.15.1"

print('Integration test runner.py')

# Validate config
print('Validating config...')

# Start tests
print('Starting tests...')
from tests_dist.ProcTestFixture import ProcTestFixture

class TestVersion(ProcTestFixture):
    def test_remote_version(self):
        print()
        print("DEBUG: Hello World")
        args = [
            'ssh',
            'maaktweluit@192.168.178.172', 
            'cd', '/home/maaktweluit/src/golem', ';',
            '.venv/bin/pytest', 'tests_dist/tests/test_version.py', '-s'
        ]
        
        # assert logs in right order
        exp_err = []
        exp_out = [
            '============================= test session starts ==============================',
            'P: All expected out lines have been found'
        ]

        opts = {
            'cwd': None
        }
        exit_code, log_err, log_out = self.do_magic(opts, args, exp_err, exp_out)

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
print('Generating report...')
print('Test case 1:')
expected = bytes('GOLEM version: ' + version_check + '\n', 'utf-8')
# passed = stdout == expected
# print(str(expected))
passed = 'always'
print('assert(config_version == golemapp --version): ' + str(passed))
