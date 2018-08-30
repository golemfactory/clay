from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run

# actually, what this is supposed to do is to:
# 1. copy code from resources_dir to output_dir
# 2. run python3 on main_file in output_dir


code_file = os.path.join(params.RESOURCES_DIR, params.main_file)
f = imp.load_source("f", code_file)

solution = f.run(*params.args, **params.kwargs)
result_path = os.path.join(params.OUTPUT_DIR, params.out_file)

with open(result_path, "w") as f:
    f.write("{}".format(solution))