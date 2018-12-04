from __future__ import print_function

import imp
import json
import os


with open('/golem/work/params.json', 'r') as params_file:
    params = json.load(params_file)


def run(data_files, subtask_data, difficulty, result_size, result_file):
    code_file = os.path.join(params['RESOURCES_DIR'], "code", "computing.py")
    computing = imp.load_source("code", code_file)

    data_file = os.path.join(params['RESOURCES_DIR'], "data", data_files[0])
    result_path = os.path.join(params['OUTPUT_DIR'], result_file)

    solution = computing.run_dummy_task(data_file,
                                        subtask_data,
                                        difficulty,
                                        result_size)

    # TODO try catch and log errors. Issue #2425
    with open(result_path, "w") as f:
        f.write("{}".format(solution))


run(params['data_files'],
    params['subtask_data'],
    params['difficulty'],
    params['result_size'],
    params['result_file'])
