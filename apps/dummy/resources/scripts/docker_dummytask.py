from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run


def run(data_files, subtask_data, difficulty, result_size, result_file):

    print("DIRS ", str(os.listdir("/")))
    print("DIRS ", str(os.listdir(params.RESOURCES_DIR)))
    print("DIRS ", str(os.listdir("{}/code".format(params.RESOURCES_DIR))))
    print("DIRS ", str(os.listdir(params.OUTPUT_DIR)))

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

    time.sleep(3)

    if difficulty == 0xffff0000:
        for _ in range(10):
            time.sleep(1)
            for fname in os.listdir(params.MESSAGES_IN_DIR):
                if not fname.startswith("."):
                    with open(os.path.join(params.MESSAGES_IN_DIR, fname), "r") as f:
                        print(os.path.join(params.MESSAGES_IN_DIR, fname))
                        x = f.read()
                        print(x)
                        x = json.loads(x)
                    with open(os.path.join(params.MESSAGES_OUT_DIR, fname + "out"), "w+") as f:
                        json.dump({"got_messages": x["got_messages"] + "bbb"}, f)


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
