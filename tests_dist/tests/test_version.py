import json

from tests_dist.ProcTestFixture import ProcTestFixture

class TestVersion(ProcTestFixture):

    def test_golemapp_version(self):
        print()
        print("DEBUG: Hello World")
        config = {}
        with open('./tests_dist/tests/config.json') as f:
            config = json.load(f)
        # do magic
        args = ['golemapp', '--version']
        
        # assert logs in right order
        exp_err = []
        exp_out = [
            'GOLEM version: ' + config['version']
        ]

        exit_code, log_err, log_out = self.do_magic(config, args, exp_err, exp_out)

        print("DEBUG: OUT:" + str(len(log_out)))
        print(log_out)
        print("DEBUG: ERR:" + str(len(log_err)))
        print(log_err)
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

