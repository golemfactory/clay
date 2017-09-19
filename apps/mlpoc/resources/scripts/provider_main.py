import json
import os
import sys

import params

sys.path.append(os.path.join(params.RESOURCES_DIR, "code", "impl"))
sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
sys.path.append(os.path.join(params.WORK_DIR)) # for params.py and messages.py

from impl import model

def evaluate_network():
    return 1.0  # TODO finish that function

def run():
    data_file = os.path.join(params.RESOURCES_DIR, "data", params.data_file)

    runner = model.HonestModelRunner(params.OUTPUT_DIR, data_file)
    runner.run_full_training()
    score = evaluate_network()
    return score

score = run()

with open(os.path.join(params.OUTPUT_DIR, "result" + params.RESULT_EXT), "w") as f:
    json.dump({score: params.network_configuration}, f)