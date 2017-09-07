import os
import sys

import params

sys.path.append(os.path.join(params.RESOURCES_DIR, "code", "impl"))
sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
sys.path.append(os.path.join(params.WORK_DIR)) # for params.py and messages.py

from impl import model


def run():
    data_file = os.path.join(params.RESOURCES_DIR, "data", params.data_files[0])
    # this if is not strictly needed, but it is useful for debugging purposes
    # IT DOESN"T WORK BECAUSE THE RESOURCES FILESYSTEM IS READ-ONLY
    # if not os.path.exists(os.path.join(params.RESOURCES_DIR, "code", "impl", "params.py")):
    #     os.symlink(os.path.join(params.WORK_DIR, "params.py"), os.path.join(params.RESOURCES_DIR, "code", "impl", "params.py"))
    runner = model.HonestModelRunner(params.OUTPUT_DIR, data_file)
    runner.run_full_training()

run()
