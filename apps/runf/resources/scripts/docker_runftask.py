import os
import sys
import cloudpickle as pickle

import params  # This module is generated before this script is run

sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
sys.path.append(os.path.join(params.WORK_DIR))  # for messages.py


# actually, what this is supposed to do is to:
# 1. copy code from resources_dir to output_dir
# 2. run python3 on main_file in output_dir


code_file = os.path.join(params.RESOURCES_DIR, params.main_file)
with open(code_file, "rb") as f:
    func = pickle.load(f)

solution = func(*params.args, **params.kwargs)
result_path = os.path.join(params.OUTPUT_DIR, params.out_file)

with open(result_path, "w") as f:
    f.write("{}".format(solution))
