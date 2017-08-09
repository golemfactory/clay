from __future__ import print_function

import os
# import importlib.util
import platform
import imp

# import computing
import params  # This module is generated before this script is run

OUTPUT_DIR = "/golem/output"
WORK_DIR = "/golem/work"  # we don't need that, all the work is done in memory
RESOURCES_DIR = "/golem/resources"


def run(data_files, subtask_data, difficulty, result_size, result_file, shared_data_size):  # TODO types

    code_file = os.path.join(RESOURCES_DIR, "code", "computing.py")
    # spec = importlib.util.spec_from_file_location("code", code)
    # computing_module = importlib.util.module_from_spec(spec)
    # spec.loader.exec_module(computing_module)

    # raise Exception(code, os.listdir(RESOURCES_DIR))# os.listdir( os.path.join(RESOURCES_DIR, "resources")))#, os.listdir(RESOURCES_DIR + "/resources"), os.listdir(RESOURCES_DIR) + "/resources/code")
    computing = imp.load_source("code", code_file)

    assert (len(subtask_data) == shared_data_size)

    data_file = os.path.join(RESOURCES_DIR, "data", data_files[0])
    result_path = os.path.join(OUTPUT_DIR, result_file)

    solution = computing.run_dummy_task(data_file, subtask_data, difficulty, result_size)

    with open(result_path, "w") as f: # TODO try catch and log errors
        f.write("{}".format(solution))


# TODO send subtask data as string!
run(params.data_files, params.subtask_data, params.difficulty, params.result_size, params.result_file,
    params.subtask_data_size)
