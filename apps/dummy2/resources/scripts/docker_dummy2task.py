from __future__ import print_function

import imp
import os

# pylint: disable=import-error
import params  # This module is generated before this script is run


def run(_data_files, subtask_data, difficulty, result_size, result_file):
    code_file = os.path.join(params.RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)
    result_path = os.path.join(params.OUTPUT_DIR, result_file)

    solution = computing.run_dummy2_task(None,
                                         subtask_data,
                                         difficulty,
                                         result_size)

    # TODO try catch and log errors. Issue #2425
    with open(result_path, "w") as f:
        f.write("{}".format(solution))


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
