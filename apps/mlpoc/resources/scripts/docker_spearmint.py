# It has to run on the local machine
# because colluding can be a real danger in this setting
# but <del> Spearmint shouldn't be very resources-heavy </del>
# Spearmint CAN be resources-heavy
# but i guess that's all we have for now

import os
import subprocess
import time

import params


# copied from dirmanager.py
# but it is difficult to avoid duplication here
def ls_R(dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(dir, followlinks=True):
        for name in filenames:
            files.append(os.path.join(dirpath, name))
    return files


# TODO change the way parameters are passed to spearmint
# noiseless parameter should be based on some input from user
# not hardcoded here. Method should also not be hardcoded here.
def run_one_update():
    # cmd = "/usr/bin/python /opt/spearmint/spearmint-lite/spearmint-lite.py {} " \
    #       "--method=GPEIOptChooser --method-args=mcmc_iters=10,noiseless=1"\
    #       .format(params.EXPERIMENT_DIR)
    cmd = "/usr/bin/python /opt/spearmint/spearmint-lite/spearmint-lite.py {}".format(params.EXPERIMENT_DIR)
    try:
        subprocess.check_output(cmd, shell=True)
    except subprocess.CalledProcessError as e:
        print(e.output)
        raise Exception("Updating spearmint went wrong")


# check if any new messages were added - if yes, update results.dat file
def run():
    while (True):
        time.sleep(params.EVENT_LOOP_SLEEP)
        signal_files = os.listdir(params.SIGNAL_DIR)
        if signal_files:
            for f in signal_files:
                run_one_update()
                # signal file has to be removed AFTER updating
                os.remove(os.path.join(params.SIGNAL_DIR, f))


run()
