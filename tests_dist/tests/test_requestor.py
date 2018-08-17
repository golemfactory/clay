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
                'cmd': ['golemapp', '--password', 'a', '--accept-terms', '--concent', 'disabled', '--protocol_id', '1616'],
                'type': 'cmd',
                'channel': 0,
                'err': [
                    'INFO     [golemapp                           ] GOLEM Version: ' + self.config["version"],
                    'INFO     [golem.node                         ] Got password',
                    'INFO     [golem.client                       ] Golem is listening on ports: P2P=40102, Task=40103, Hyperdrive=3282',
                ],
                'out': [],
                'done': 'err'
            },
            {
                'cmd':['golemcli', 'tasks', 'create', os.path.dirname(os.path.abspath(__file__)) + os.path.sep + 'blender-bmw-simple.json'],
                'type': 'cmd',
                'channel': 1,
                'err': [],
                'out': [],
                'done': 'exit 0'
            },
            {
                'type': 'check',
                'channel': 0,
                'err': [
                    "^WARNING  [golem.transactions.ethereum.fundslocker] I can't remove payment lock for subtask from task",
                ],
                'out': [],
                'done': 'err'
            },
            {
                'signal':  signal.CTRL_C_EVENT,
                'type': 'signal',
                'channel': 0,
                'err': [],
                'out': [],
                'done': 'exit 0'
            }
        ]

        test = tSession(
            opts,
            script
        )
        self._tests = [test]

        while not test.tick():
            time.sleep(0.1)

        exit_code, log_err, log_out = test.report()[0]

        # assert final test state
        assert exit_code == 0
        print("P: Exit code is 0")
        assert len(log_out) >= 3
        print("P: ./golemapp stdout returns more then 3 lines")
        err_len = len(log_err)
        assert len(log_err) >= 1
        print("P: ./golemapp stderr is not empty")
