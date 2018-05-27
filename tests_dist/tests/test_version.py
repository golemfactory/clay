import json
import time
import subprocess

def run(args, config):
    proc = subprocess.Popen(
        args,
        cwd='dist/' + config["dist_dir"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    return proc

class TestVersion:

    @staticmethod
    def test_golemapp_version():
        print()
        print("DEBUG: Hello World")
        config = {}
        with open('./tests_dist/tests/config.json') as f:
            config = json.load(f)
        log_err = []
        log_out = []
        exit_code = None
        # do magic
        proc = run(['golemapp', '--version'], config)
        
        # assert logs in right order
        expect_err = []
        expect_out = [
            'GOLEM version: ' + config['version']
        ]

        check_err_log = 0
        check_err_exp = 0
        check_out_log = 0
        check_out_exp = 0
        while True:
            # streams to logs
            err_line = proc.stderr.readline()
            while err_line and len(err_line) > 0:
                if err_line:
                    log_err.append(err_line.decode('utf-8').replace('\n',''))
                err_line = proc.stderr.readline()

            out_line = proc.stdout.readline()
            while out_line and len(out_line) > 0:
                if out_line:
                    log_out.append(out_line.decode('utf-8').replace('\n',''))
                out_line = proc.stdout.readline()

            # check logs for next assert
            while len(log_err) > check_err_log:
                if expect_err:
                    cur_err = log_err[check_err_log]
                    if cur_err == expect_err[check_err_exp]:
                        # foundd expected line
                        check_err_exp+=1
                check_err_log+=1

            while len(log_out) > check_out_log:
                print("DEBUG: Checking log line: " + str(check_out_log))
                if expect_out:
                    cur_out = log_out[check_out_log]
                    print("DEBUG: compare")
                    print(cur_out)
                    print(expect_out[check_out_exp])
                    if cur_out == expect_out[check_out_exp]:
                        # foundd expected line
                        print("P: Found match '{}'".format(cur_out))
                        check_out_exp+=1
                check_out_log+=1

            tick = proc.poll()
            if tick is not None:
                exit_code = tick
                print("DEBUG: Exit code=" + str(tick))
                break
            time.sleep(0.1)

        assert check_out_exp == len(expect_out)
        print("P: All expected out lines have been found")

        assert check_err_exp == len(expect_err)
        print("P: All expected err lines have been found")

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

