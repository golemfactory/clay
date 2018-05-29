import subprocess
import time
import unittest

def _clean_line(line):
    return line.decode('utf-8').replace('\n', '')

def _empty_stream(_out, _in):
    line = _in.readline()
    while line and len(line) > 0:
        _out.append(_clean_line(line))
        line = _in.readline()

class ProcTestFixture(unittest.TestCase):

    def do_magic(self, opts, args, exp_err, exp_out):

        exit_code = None
        log_err = []
        log_out = []
        
        proc = subprocess.Popen(
            args,
            cwd=opts['cwd'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

        check_err_log = 0
        check_err_exp = 0
        check_out_log = 0
        check_out_exp = 0
        while True:
            # streams to logs
            _empty_stream(log_err, proc.stderr)
            _empty_stream(log_out, proc.stdout)

            # check logs for next assert
            while len(log_err) > check_err_log and len(exp_err) > check_err_exp:
                if exp_err:
                    cur_err = log_err[check_err_log]
                    if cur_err == exp_err[check_err_exp]:
                        # foundd expected line
                        check_err_exp+=1
                check_err_log+=1

            while len(log_out) > check_out_log and len(exp_out) > check_out_exp:
                print("DEBUG: Checking log line: " + str(check_out_log))
                if exp_out:
                    cur_out = log_out[check_out_log]
                    print("DEBUG: compare")
                    print(cur_out)
                    print(exp_out[check_out_exp])
                    if cur_out == exp_out[check_out_exp]:
                        # foundd expected line
                        print("P: Found match '{}'".format(cur_out))
                        check_out_exp+=1
                check_out_log+=1

            tick = proc.poll()
            if tick is not None:
                exit_code = tick
                print("DEBUG: Exit code=" + str(tick))
                break
            time.sleep(0.1)

#        assert check_out_exp == len(exp_out)
        print("P: All expected out lines have been found")

#        assert check_err_exp == len(exp_err)
        print("P: All expected err lines have been found")

        return exit_code, log_err, log_out
