# It has to run on the local machine
# because colluding can be a real danger in this setting
# but <del> Spearmint shouldn't be very resources-heavy </del>
# Spearmint CAN be resources-heavy
# but i guess that's all we have for now

import subprocess
import time
import os

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
    # DEBUG
    # print("Updating suggestions...")
    # print(os.path.isfile("/usr/bin/python"))
    # print(os.path.exists("/opt"))
    # print(os.listdir("/opt"))
    # print(os.path.exists("/opt/spearmint"))
    # print(os.listdir("/opt/spearmint"))
    # print(os.path.exists("/opt/spearmint/spearmint-lite"))
    # print(os.listdir("/opt/spearmint/spearmint-lite"))
    # print(os.path.exists("/opt/spearmint/spearmint-lite/spearmint-lite.py"))
    # print("aaas")
    # print(os.path.exists(params.EXPERIMENT_DIR))
    # print(os.listdir(params.EXPERIMENT_DIR))
    # output = ""

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
                for _ in range(params.SIMULTANEOUS_UPDATES_NUM):
                    run_one_update()
                os.remove(os.path.join(params.SIGNAL_DIR, f))  # signal file has to be removed AFTER updating

run()
