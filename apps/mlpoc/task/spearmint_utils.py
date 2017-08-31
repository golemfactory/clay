# based on braninpy from https://github.com/JasperSnoek/spearmint/blob/master
# /spearmint-lite/braninpy/braninrunner.py  # noqa
# author: Jasper Snoek

import json
import math
import os
import shutil
from collections import OrderedDict

RESULT_FILE = "results.dat"
CONFIG = "config.json"


def f(x):
    return x * math.log(x)


def run_one_evaluation(directory, params):
    # for now, params are param -> values
    # but we need values -> param
    params = OrderedDict((tuple(v), k) for k, v in sorted(params.items()))
    print("Evaluation...")
    with open(os.path.join(directory, RESULT_FILE), 'r') as resfile:
        newlines = []
        for line in resfile.readlines():
            values = line.split()
            if len(values) < 3:
                continue
            val = values.pop(0)
            dur = values.pop(0)
            X = values

            if val == 'P' and val in params:
                val = params[val]
                newlines.append("{} 1 {}\n".format(val, float(values[0])))
            else:
                newlines.append(line)

    with open(os.path.join(directory, RESULT_FILE), 'w') as outfile:
        outfile.writelines(newlines)


def create_conf(directory):
    conf = OrderedDict([("X", {"name": "X",
                              "type": "float",
                              "min": 0.1,
                              "max": 5.0,
                              "size": 1
                              })])
    with open(os.path.join(directory, CONFIG), "w+") as f:
        json.dump(conf, f)


def clean_res(directory):
    shutil.rmtree(directory)


def extract_results(directory):
    xs = []
    ys = []
    with open(os.path.join(directory, RESULT_FILE), 'r') as resfile:
        for line in resfile.readlines():
            values = line.split()
            if len(values) < 3:
                continue
            y = values.pop(0)
            dur = values.pop(0)
            x = values[0]
            if dur == 'P':
                continue
            else:
                xs.append(x)
                ys.append(y)
    return xs, ys
