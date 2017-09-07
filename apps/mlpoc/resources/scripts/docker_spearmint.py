# It has to run on the local machine
# because colluding can be real danger in this setting
# but <del> Spearmint shouldn't be very resources-heavy </del>
# Spearmint CAN be resources-heavy
# but i guess that's all we have

import os
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
def run_one_update():
    print("Updating suggestions...")
    cmd = "python /opt/spearmint/spearmint-lite/spearmint-lite.py {} " \
          "--method=GPEIOptChooser --method -args=mcmc_iters=10," \
          "noiseless=1".format(params.EXPERIMENT_DIR)
    os.subprocess.call(cmd)


# check if any new messages were added - if yes, update results.dat file
def run():
    while (True):
        time.sleep(params.EVENT_LOOP_SLEEP)
        if os.path.exists(params.SIGNAL_FILE):
            os.remove(params.SIGNAL_FILE)
            for _ in range(params.SIMULTANEOUS_UPDATES_NUM):
                run_one_update()


run()
