import time
import subprocess

dist_name="golem-0.15.1+dev254.g7154f6c5c"
version_check="0.15.1"

print('Integration test runner.py')

# Validate config
print('Validating config...')

# Start tests
print('Starting tests...')
proc = subprocess.Popen(
        ['golemapp', '--version'],
        cwd='dist/'+dist_name,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

stdout = bytes()
stderr = bytes()

print('Polling tests...')
while proc.poll() is None:
    stdout += proc.stdout.read()
    stderr += proc.stderr.read()
    time.sleep(0.1)
print('Tests Completed!')

# Poll results
print('Monitoring results...')

print("OUT:")
print(str(stdout))

print("ERR:")
print(str(stderr))

# Print report
print('Generating report...')
print('Test case 1:')
expected = bytes('GOLEM version: ' + version_check + '\n', 'utf-8')
passed = stdout == expected
# print(str(expected))
print('assert(config_version == golemapp --version): ' + str(passed))
