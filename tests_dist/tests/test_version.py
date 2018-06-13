import json

from tests_dist.lib import TestSession, CleanupFixture

class TestVersion (CleanupFixture):

    def test_golemapp_version(self):
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
                'cmd': ['./golemapp', '--version'],
                'type': 'cmd',
                'err': [],
                'out': [
                    'GOLEM version: ' + config['version']
                ],
                'done': 'out'
            },
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
        assert len(log_out) == 1 
        print("P: Version returns one line")
        err_len = len(log_err)
        assert len(log_err) <= 5 
        if err_len > 0:
            print("W: Version does not expect stderr")
        else:
            print("P: Version stderr is empty")

