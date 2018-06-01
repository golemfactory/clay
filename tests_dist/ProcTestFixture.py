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

    def init_magic(self, opts, args):
        self.proc = subprocess.Popen(
            args,
            cwd=opts['cwd'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)

    def tick_magic(self):
        log_err = []
        log_out = []
        # streams to logs
        _empty_stream(log_err, self.proc.stderr)
        _empty_stream(log_out, self.proc.stdout)

        tick = self.proc.poll()
        return tick, log_err, log_out
