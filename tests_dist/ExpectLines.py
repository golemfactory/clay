
class ExpectLines:

    def __init__(self, err, out):
        self.exp_err = err
        self.exp_out = out

        self.check_err_log = 0
        self.check_err_exp = 0
        self.check_out_log = 0
        self.check_out_exp = 0

    def feed(self, log_err, log_out):
        while len(log_err) > self.check_err_log and len(self.exp_err) > self.check_err_exp:
            if self.exp_err:
                cur_err = log_err[self.check_err_log]
                if cur_err == self.exp_err[self.check_err_exp]:
                    # foundd expected line
                    self.check_err_exp+=1
            self.check_err_log+=1

        while len(log_out) > self.check_out_log and len(self.exp_out) > self.check_out_exp:
            # print("DEBUG: Checking log line: " + str(self.check_out_log))
            if self.exp_out:
                cur_out = log_out[self.check_out_log]
                # print("DEBUG: compare")
                # print(cur_out)
                # print(self.exp_out[self.check_out_exp])
                if cur_out == self.exp_out[self.check_out_exp]:
                    # foundd expected line
                    print("P: Found match '{}'".format(cur_out))
                    self.check_out_exp+=1
            self.check_out_log+=1

    def report(self):
        assert self.check_out_exp == len(self.exp_out)
        print("P: All expected out lines have been found")

        assert self.check_err_exp == len(self.exp_err)
        print("P: All expected err lines have been found")
