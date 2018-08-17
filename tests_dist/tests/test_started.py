import json
import os
import signal
import time

from tests_dist.lib import tSession, CleanupFixture, ConfigFixture

class TestStarted(CleanupFixture, ConfigFixture):

    def test_golem_start(self):
        print()
        print("DEBUG: Hello World")

        opts = {
            'dist_name': self.config["dist_name"]
        }
        script = [
            {
                'cmd': ['golemapp', '--password', 'a', '--accept-terms', '--concent', 'disabled'],
                'type': 'cmd',
                'err': [
                    'INFO     [golemapp                           ] GOLEM Version: ' + self.config["version"],
                    'INFO     [golem.node                         ] Got password',
                    'INFO     [golem.client                       ] Starting network ...',
                    'INFO     [golem.client                       ] Golem is listening on ports: P2P=40102, Task=40103, Hyperdrive=3282',
                ],
                'out': [],
                'done': 'err'
            },
            {
                'signal': signal.CTRL_C_EVENT if os.name == 'nt' else signal.SIGINT,
                'type': 'signal',
                'err': [
                    'WARNING  [twisted                            ] Native worker received SIGTERM - shutting down ..',
                ],
                'out': [],
                'done': 'exit 0'
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
        assert exit_code == 0
        print("P: Exit code is 0")
        assert len(log_out) >= 0
        print("P: ./golemapp stdout returns 0 or more lines")
        err_len = len(log_err)
        assert len(log_err) >= 1
        print("P: ./golemapp stderr is not empty")
