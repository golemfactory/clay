import json

from tests_dist.lib import TestSession, CleanupFixture

class TestStarted(CleanupFixture):

    def test_golem_start(self):
        print()
        print("DEBUG: Hello World")

        config = {}
        with open('./tests_dist/tests/config.json') as f:
            config = json.load(f)

        opts = {
            'cwd': 'dist/' + config["dist_dir"]
        }
        script = [
            {
                'cmd': ['./golemapp', '--password', 'a', '--accept-terms', '--concent', 'disabled'],
                'type': 'cmd',
                'err': [
                    'INFO     [golemapp                           ] GOLEM Version: ' + config["version"],
                    'INFO     [app                                ] Got password'
                ],
                'out': [],
                'done': 'err'
            },
            {
                'signal': 2, #  SIGINT
                'type': 'signal',
                'err': [],
                'out': [],
                'done': 'exit 1'
            }
        ]

        test = TestSession(
            opts,
            script
        )
        self._tests = [test]

        while True:
            if test.tick() is not None:
                break

        exit_code, log_err, log_out = test.report()

        # assert final test state
        assert exit_code == 0
        print("P: Exit code is 0")
        assert len(log_out) == 3
        print("P: ./golemapp stdout returns 3 lines")
        err_len = len(log_err)
        assert len(log_err) >= 1
        print("P: ./golemapp stderr is not empty")

