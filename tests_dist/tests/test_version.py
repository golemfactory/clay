import json

from tests_dist.ProcTestFixture import ProcTestFixture
from tests_dist.ExpectLines import ExpectLines

class TestVersion(ProcTestFixture):

    def test_golemapp_version(self):
        print()
        print("DEBUG: Hello World")
        config = {}
        with open('./tests_dist/tests/config.json') as f:
            config = json.load(f)
        # do magic
        args = ['./golemapp', '--version']
        
        # assert logs in right order
        exp_err = []
        exp_out = [
            'GOLEM version: ' + config['version']
        ]

        opts = {
            'cwd': 'dist/' + config["dist_dir"]
        }

        self.init_magic(opts, args)
        expect_lines = ExpectLines(exp_err, exp_out)
        log_err = []
        log_out = []

        while True:
            exit_code, tmp_err, tmp_out = self.tick_magic()
            # expect stuff
            expect_lines.feed(tmp_err, tmp_out)
            # store stuff
            if tmp_err:
                log_err += tmp_err
            if tmp_out:
                log_out += tmp_out
            # are we there yet?
            if exit_code is not None:
                break

        expect_lines.report()


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

