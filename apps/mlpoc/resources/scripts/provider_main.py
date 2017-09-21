import json
import os
import sys

import params

from sklearn.metrics import accuracy_score
from torch import nn, torch, from_numpy
from torch.autograd import Variable


sys.path.append(os.path.join(params.RESOURCES_DIR, "code", "impl"))
sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))
sys.path.append(os.path.join(params.WORK_DIR)) # for params.py and messages.py

from impl import model


def evaluate_network(model_runner: model.HonestModelRunner):
    # FIXME quite ugly, should be a function of Model
    x, y_true = model_runner.batch_manager.get_full_testing_set()
    x = Variable(from_numpy(x).view(len(x), -1).type(torch.FloatTensor))
    y_pred = model_runner.model.net(x)
    y_pred = y_pred.data.numpy()

    return accuracy_score(y_true.argmax(1), y_pred.argmax(1))


def run():
    data_file = os.path.join(params.RESOURCES_DIR, "data", params.data_file)

    runner = model.HonestModelRunner(params.OUTPUT_DIR, data_file)
    runner.run_full_training()
    score = evaluate_network(runner)
    return score


score = run()

with open(os.path.join(params.OUTPUT_DIR, "result" + params.RESULT_EXT), "w") as f:
    json.dump({score: params.network_configuration}, f)