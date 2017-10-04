from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run

OUTPUT_DIR = "/golem/output"
WORK_DIR = "/golem/work"  # we don't need that, all the work is done in memory
RESOURCES_DIR = "/golem/resources"


def run(data_files, subtask_data, difficulty, result_size, result_file):
    code_file = os.path.join(RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)

    data_file = os.path.join(RESOURCES_DIR, "data", data_files[0])
    result_path = os.path.join(OUTPUT_DIR, result_file)

    solution = computing.run_dummy_task(data_file,
                                        subtask_data,
                                        difficulty,
                                        result_size)

    with open(result_path, "w") as f:  # TODO try catch and log errors
        f.write("{}".format(solution))


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
