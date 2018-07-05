import json
import signal
import os
import time

from tests_dist.lib import tSession, CleanupFixture, ConfigFixture

class TestStartedHalf(CleanupFixture, ConfigFixture):

    def test_golem_start_half(self):
        print()
        print("DEBUG: Hello World")
        def handler(signum, frame):
            print("CTRL + C received")
            time.sleep(10)
            signal.default_int_handler(signum, frame)

        signal.signal(signal.SIGINT, handler)
        opts = {
            'dist_name': self.config["dist_name"]
        }
        expected_exit = 2 if os.name == 'nt' else 1
        script = [
            {
                'cmd': ['golemapp', '--password', 'a', '--accept-terms', '--concent', 'disabled'],
                'type': 'cmd',
                'err': [
                    'INFO     [golemapp                           ] GOLEM Version: ' + self.config["version"],
                    'INFO     [golem.node                         ] Got password'
                ],
                'out': [],
                'done': 'err'
            },
            {
                'signal':  signal.SIGINT,
                'type': 'signal',
                'err': [
                    # TODO: Count be uncommented with CTRL_C_EVENT ? 'Aborted!',
                ],
                'out': [],
                'done': 'exit ' + str(expected_exit)
            }
        ]

        test = tSession(
            opts,
            script
        )
        self._tests = [test]

        while test.tick() is False:
            time.sleep(0.1)

        exit_code, log_err, log_out = test.report()[0]

        # assert final test state
        assert exit_code == expected_exit
        print("P: Exit code is 1")
        assert len(log_out) == 0
        print("P: ./golemapp stdout returns 0 lines")
        err_len = len(log_err)
        assert len(log_err) >= 1
        print("P: ./golemapp stderr is not empty")
