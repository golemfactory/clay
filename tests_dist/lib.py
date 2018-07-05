# TestSession
class tSession:
    def __init__(self, opts, script):
        self.step = -1
        self.script = script
        self._opts = opts
        self._last_step = len(script)
        self._completed_channels = []

        self._proc_tester = []
        self._expect_lines = []
        self.log = []

        self.next_step()
        print('DEBUG: Test session created')

    def tick(self):
        ticks = len(self._proc_tester)
        channel = 0

        while channel < ticks:
            if self._completed_channels[channel] is False:
                exit_code, tmp_err, tmp_out = self._proc_tester[channel].tick()
                print('DEBUG: Got lines: err=' + str(len(tmp_err)) + ' out=' + str(len(tmp_out)) + ', code='+str(exit_code))
                # expect stuff
                self._expect_lines[channel].feed(tmp_err, tmp_out)
                # store stuff
                _log = self.log[channel]
                _log.err += tmp_err
                _log.out += tmp_out
                _log.exit_code = exit_code
                if exit_code is not None:
                    self._completed_channels[channel] = True

                self.test_step(channel)
            channel += 1
        last_step = (self._last_step <= self.step + 1)
        all_done = all(self._completed_channels)
        print('DEBUG: tick() END ' + str(last_step) + str(all_done))
        return last_step and all_done

    def test_step(self, channel):
        print('DEBUG: test_step()')
        _step = self.script[self.step]
        _log = self.log[channel]
        _expect_lines = self._expect_lines[channel]

        if _step['done'] == 'err':
            print('DEBUG: Testing err...')
            print('DEBUG: ' + str(len(_expect_lines.exp_err)))
            print('DEBUG: ' + str(_expect_lines.check_err_exp))
            if len(_expect_lines.exp_err) == _expect_lines.check_err_exp:
                print('DEBUG: Expected err matches, next step')
                self.next_step()
            else:
                print('DEBUG: Not all lines are found yet, waiting...')

        elif _step['done'] == 'out':
            print('DEBUG: Testing out...')
            print('DEBUG: ' + str(len(_expect_lines.exp_out)))
            print('DEBUG: ' + str(_expect_lines.check_out_exp))
            if len(_expect_lines.exp_out) == _expect_lines.check_out_exp:
                print('DEBUG: Expected out matches, next step')
                self.next_step()
            else:
                print('DEBUG: Not all lines are found yet, waiting...')

        elif _step['done'][:4] == 'exit':
            print('DEBUG: Testing exit...')
            if _log.exit_code is None:
                print('DEBUG: No exit yet, waiting...')
            elif _log.exit_code == int(_step['done'][-1:]):
                print('DEBUG: Exit code matches, next step')
                self.next_step()
            else:
                print('F: Exit code does not match expected for this step')


    def next_step(self):
        print('DEBUG: next_step() ' + str(self.step))
        if self._last_step <= self.step + 1:
            print('DEBUG: No more steps')
            return
        # Increment the step
        self.step += 1
        _step = self.script[self.step]
        channel = int(_step['channel']) if 'channel' in _step else 0

        print('DEBUG:  type = ' + _step['type'])
        if _step['type'] == 'cmd':
            print('DEBUG:  cmd = ' + repr(_step['cmd']))
            print('DEBUG:  err = ' + repr(_step['err']))
            print('DEBUG:  out = ' + repr(_step['out']))
            # TODO: ensure channel no is correct
            self.log.append(TestLog())
            self._proc_tester.append(ProcTester(self._opts, _step['cmd']))
            self._expect_lines.append(ExpectLines(_step['err'], _step['out']))
            self._completed_channels.append(False)
        elif _step['type'] == 'check':
            if self._proc_tester[channel] is None:
                raise "Can not check output when there is no proc_tester"
            
            print('DEBUG:  err = ' + repr(_step['err']))
            print('DEBUG:  out = ' + repr(_step['out']))

            self._expect_lines[channel] = ExpectLines(_step['err'], _step['out'])
        elif _step['type'] == 'signal':
            if self._proc_tester[channel] is None:
                raise "Can not send signal when there is no proc_tester"

            print('DEBUG:  signal = ' + repr(_step['signal']))
            self._expect_lines[channel] = ExpectLines(_step['err'], _step['out'])
            self._proc_tester[channel].signal(int(_step['signal']))


    def report(self):
        print('DEBUG: report()')
        ticks = len(self._expect_lines)
        channel = 0

        result = []

        while channel < ticks:
            self._expect_lines[channel].report()

            _log = self.log[channel]
            log_err = _log.err
            log_out = _log.out

            print("DEBUG: OUT:" + str(len(log_out)))
            print(log_out)
            print("DEBUG: ERR:" + str(len(log_err)))
            print(log_err)
            result.append( (_log.exit_code, log_err, log_out) )
            channel += 1

        return result

    def quit(self):
        ticks = len(self._proc_tester)
        channel = 0

        while channel < ticks:
            self._proc_tester[channel].quit()
            channel += 1

class TestLog:
    def __init__(self):
        self.err = []
        self.out = []
        self.exit_code = None

# ProcTester
import os
import subprocess
import sys
import time

def _clean_line(line):
    # result = line.strip()
    result = line.decode('utf-8').strip()
    print('DEBUG: Clean line=' + result)
    return result

def _empty_stream(_out, _in):
    #print('DEBUG: _empty_stream() START')
    line = _in.readline(0.1)
    while line and len(line) > 0:
        #print('DEBUG: _empty_stream() loop: ' + line)
        _out.append(_clean_line(line))
        line = _in.readline(0.1)
    #print('DEBUG: _empty_stream() END')

class ProcTester:

    def __init__(self, opts, args):

        print("DEBUG: Starting new ProcTester" + repr(args))
        if 'dist_name' in opts:
            # print("DEBUG: PATH" + repr(os.environ['PATH']))
            test_path = os.getcwd() + os.path.sep + 'dist' + os.path.sep + opts["dist_name"]
            os.environ['PATH'] = test_path + os.pathsep + os.environ['PATH']
            # print("DEBUG: PATH" + repr(os.environ['PATH']))

        kwargs = dict(
            env=os.environ,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            kwargs['startupinfo'] = startupinfo
            # kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP

        try:
            self.proc = subprocess.Popen(args, **kwargs)

            self.out = NonBlockingStreamReader(self.proc.stdout)
            self.err = NonBlockingStreamReader(self.proc.stderr)
        except Exception as e:
            print("ERROR" + str(e))

    def tick(self):
        log_err = []
        log_out = []

        # streams to logs
        _empty_stream(log_err, self.err)
        _empty_stream(log_out, self.out)

        exit_code = self.proc.poll()
        return exit_code, log_err, log_out

    def signal(self, signal):
        #self.proc.sendcontrol('c')
        os.kill(self.proc.pid, signal)

    def quit(self):
        self.out.quit()
        self.err.quit()
        self.proc.kill()

# ExpectLines
class ExpectLines:

    def __init__(self, err, out):
        self.exp_err = err
        self.exp_out = out

        self.check_err_exp = 0
        self.check_out_exp = 0

    def feed(self, log_err, log_out):
        print('DEBUG: feed()')

        self.check_err_log = 0
        self.check_out_log = 0

        while len(log_err) > self.check_err_log and len(self.exp_err) > self.check_err_exp:
            if self.exp_err:
                cur_err = log_err[self.check_err_log]
                check_err = self.exp_err[self.check_err_exp]
                print("DEBUG: compare")
                print(cur_err)
                print(check_err)

                if check_err[:1] == '^' and cur_err.startswith(check_err[1:]):
                    # found expected line
                    print("P: Found match '{}'".format(cur_err))
                    self.check_err_exp+=1
                elif cur_err == check_err:
                    # found expected line
                    print("P: Found match '{}'".format(cur_err))
                    self.check_err_exp+=1
            self.check_err_log+=1

        while len(log_out) > self.check_out_log and len(self.exp_out) > self.check_out_exp:
            # print("DEBUG: Checking log line: " + str(self.check_out_log))
            if self.exp_out:
                cur_out = log_out[self.check_out_log]
                check_out = self.exp_out[self.check_out_exp]
                print("DEBUG: compare")
                print(cur_out)
                print(check_out)

                if check_out[:1] == '^' and cur_out.startswith(check_out[1:]):
                    # found expected line
                    print("P: Found match '{}'".format(cur_out))
                    self.check_out_exp+=1
                elif cur_out == check_out:
                    # found expected line
                    print("P: Found match '{}'".format(cur_out))
                    self.check_out_exp+=1
            self.check_out_log+=1

    def report(self):
        assert self.check_out_exp == len(self.exp_out)
        print("P: All expected out lines have been found")

        assert self.check_err_exp == len(self.exp_err)
        print("P: All expected err lines have been found")

from threading import Thread
from queue import Queue, Empty

class NonBlockingStreamReader:

    def __init__(self, stream):
        '''
        stream: the stream to read from.
                Usually a process' stdout or stderr.
        '''

        self._s = stream
        self._q = Queue()

        def _populateQueue(stream, queue):
            '''
            Collect lines from 'stream' and put them in 'quque'.
            '''

            while True:
                line = stream.readline()
                if line:
                    queue.put(line)
                else:
                    raise UnexpectedEndOfStream

        self._t = Thread(target = _populateQueue,
                args = (self._s, self._q))
        self._t.daemon = True
        self._t.start() #start collecting lines from the stream

    def readline(self, timeout = None):
        try:
            return self._q.get(block = timeout is not None,
                    timeout = timeout)
        except Empty:
            return None

    def quit(self):
        # TODO: stop thread cleanly?
        # self._t.stop()
        print('DEBUG: Not implemented yet')

class UnexpectedEndOfStream(Exception): pass

from unittest import TestCase

class CleanupFixture(TestCase):
    def __init__(self, *args, **kwargs):
        self._tests = []
        super().__init__(*args, **kwargs)

    def tearDown(self):
        for test in self._tests:
            test.quit()

import json
class ConfigFixture(TestCase):
    def __init__(self, *args, **kwargs):
        self.config = {}
        with open('./tests_dist/tests/config.json') as f:
            self.config = json.load(f)
        super().__init__(*args, **kwargs)
