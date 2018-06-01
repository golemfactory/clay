# TestSession
class TestSession:
    def __init__(self, args, opts, exp_err, exp_out):
        self.exp_err = exp_err
        self.exp_out = exp_out

        self.log_err = []
        self.log_out = []
        self.exit_code = None

        self._proc_tester = ProcTester(opts, args)
        self._expect_lines = ExpectLines(exp_err, exp_out)

    def tick(self):
        exit_code, tmp_err, tmp_out = self._proc_tester.tick()
        # expect stuff
        self._expect_lines.feed(tmp_err, tmp_out)
        # store stuff
        self.log_err += tmp_err
        self.log_out += tmp_out
        self.exit_code = exit_code

        return exit_code

    def report(self):
        self._expect_lines.report()

        log_err = self.log_err
        log_out = self.log_out

        print("DEBUG: OUT:" + str(len(log_out)))
        print(log_out)
        print("DEBUG: ERR:" + str(len(log_err)))
        print(log_err)
        # assert final test state
        assert self.exit_code == 0
        print("P: Exit code is 0")
        assert len(log_out) == 21 
        print("P: Test returns 21 lines")
        err_len = len(log_err)
        assert len(log_err) <= 5 
        if err_len > 0:
            print("W: Test does not expect stderr")
        else:
            print("P: Test stderr is empty")

# ProcTester
import subprocess
import time

def _clean_line(line):
    return line.decode('utf-8').replace('\n', '')

def _empty_stream(_out, _in):
    line = _in.readline()
    while line and len(line) > 0:
        _out.append(_clean_line(line))
        line = _in.readline()

class ProcTester:

    def __init__(self, opts, args):
        self.proc = subprocess.Popen(
            args,
            cwd=opts['cwd'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    def tick(self):
        log_err = []
        log_out = []
        # streams to logs
        _empty_stream(log_err, self.proc.stderr)
        _empty_stream(log_out, self.proc.stdout)

        tick = self.proc.poll()
        return tick, log_err, log_out

# ExpectLines
class ExpectLines:

    def __init__(self, err, out):
        self.exp_err = err
        self.exp_out = out

        self.check_err_log = 0
        self.check_err_exp = 0
        self.check_out_log = 0
        self.check_out_exp = 0

    def feed(self, log_err, log_out):
        while len(log_err) > self.check_err_log and len(self.exp_err) > self.check_err_exp:
            if self.exp_err:
                cur_err = log_err[self.check_err_log]
                if cur_err == self.exp_err[self.check_err_exp]:
                    # foundd expected line
                    self.check_err_exp+=1
            self.check_err_log+=1

        while len(log_out) > self.check_out_log and len(self.exp_out) > self.check_out_exp:
            # print("DEBUG: Checking log line: " + str(self.check_out_log))
            if self.exp_out:
                cur_out = log_out[self.check_out_log]
                # print("DEBUG: compare")
                # print(cur_out)
                # print(self.exp_out[self.check_out_exp])
                if cur_out == self.exp_out[self.check_out_exp]:
                    # foundd expected line
                    print("P: Found match '{}'".format(cur_out))
                    self.check_out_exp+=1
            self.check_out_log+=1

    def report(self):
        assert self.check_out_exp == len(self.exp_out)
        print("P: All expected out lines have been found")

        assert self.check_err_exp == len(self.exp_err)
        print("P: All expected err lines have been found")
