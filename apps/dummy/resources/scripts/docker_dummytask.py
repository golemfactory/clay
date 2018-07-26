from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run

OUTPUT_DIR = "/golem/output"
WORK_DIR = "/golem/work"  # we don't need that, all the work is done in memory
RESOURCES_DIR = "/golem/resources"

MESSAGES_IN = os.path.join(WORK_DIR, "messages_in")
MESSAGES_OUT = os.path.join(WORK_DIR, "messages_out")

def run(data_files, subtask_data, difficulty, result_size, result_file):
    code_file = os.path.join(RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)

    data_file = os.path.join(RESOURCES_DIR, "data", data_files[0])
    result_path = os.path.join(OUTPUT_DIR, result_file)

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
    # import json
    # import time
    #
    # os.makedirs(MESSAGES_IN)
    # os.makedirs(MESSAGES_OUT)
    #
    #
    # with open(os.path.join(MESSAGES_IN, "first.json"), "w+") as f:
    #     json.dump({"got_messages": "aaa"}, f)
    # with open(os.path.join(MESSAGES_OUT, "second.json"), "w+") as f:
    #     json.dump({"got_messages": "vvv"}, f)
    #
    # time.sleep(1)
    #
    # if difficulty != 0xffff0000:
    #     for _ in range(240):
    #         time.sleep(1)
    #         for fname in os.listdir(MESSAGES_IN):
    #             with open(os.path.join(MESSAGES_IN, fname), "r") as f:
    #                 x = json.load(f)
    #             with open(os.path.join(MESSAGES_OUT, fname + "out"), "w+") as f:
    #                 json.dump({"got_messages": x["got_messages"] + "bbb"}, f)


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
