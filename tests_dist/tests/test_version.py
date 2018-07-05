import time

from tests_dist.lib import tSession, CleanupFixture, ConfigFixture

class TestVersion(CleanupFixture, ConfigFixture):

    def test_golemapp_version(self):
        print()
        print("DEBUG: Hello World")

        print("DEBUG: config: "+ repr(self.config))

        opts = {
            'dist_name': self.config["dist_name"]
        }
        script = [
            {
                'cmd': ['golemapp', '--version'],
                'type': 'cmd',
                'err': [],
                'out': [
                    'GOLEM version: ' + self.config['version']
                ],
                'done': 'out'
            },
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
        assert len(log_out) == 1 
        print("P: Version returns one line")
        err_len = len(log_err)
        assert len(log_err) <= 5 
        if err_len > 0:
            print("W: Version does not expect stderr")
        else:
            print("P: Version stderr is empty")
