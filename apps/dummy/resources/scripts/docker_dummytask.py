from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run


def run(data_files, subtask_data, difficulty, result_size, result_file):
    code_file = os.path.join(params.RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)

    data_file = os.path.join(params.RESOURCES_DIR, "data", data_files[0])
    result_path = os.path.join(params.OUTPUT_DIR, result_file)

    solution = computing.run_dummy_task(data_file,
                                        subtask_data,
                                        difficulty,
                                        result_size)

    # TODO try catch and log errors. Issue #2425
    with open(result_path, "w") as f:
        f.write("{}".format(solution))

    # -------------------------------------------------------------------
    # Temporary testing for communications
    #####################################################################
    import json
    import time


    with open(os.path.join(params.MESSAGES_IN_DIR, "first.json"), "w+") as f:
        json.dump({"got_messages": "aaa"}, f)
    with open(os.path.join(params.MESSAGES_OUT_DIR, "second.json"), "w+") as f:
        json.dump({"got_messages": "vvv"}, f)

    time.sleep(1)

    if difficulty != 0xffff0000:
        for _ in range(240):
            time.sleep(1)
            for fname in os.listdir(params.MESSAGES_IN_DIR):
                with open(os.path.join(params.MESSAGES_IN_DIR, fname), "r") as f:
                    x = json.load(f)
                with open(os.path.join(params.MESSAGES_OUT_DIR, fname + "out"), "w+") as f:
                    json.dump({"got_messages": x["got_messages"] + "bbb"}, f)


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
