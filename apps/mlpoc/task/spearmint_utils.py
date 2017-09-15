# based on braninpy from https://github.com/JasperSnoek/spearmint/blob/master/spearmint-lite/braninpy/braninrunner.py  # noqa

import json
import math
import os
import shutil
from collections import OrderedDict
from typing import Tuple, List, Optional, Dict, Callable

RESULT_FILE = "results.dat"
CONFIG = "config.json"
DEFAULT_EVAL_TIME = 1 # spearmint takes into consideration evalutaion times, but we are not going to bother with that now

# dirty-state hyperparams configurations
# eg these which were already send to provider, but there is still no answer
dirties = set()


def process_lines(directory: str, f: Callable[[str, str, List[str], str], None]) -> None:
    """
    A helper function to do processing of RESULT_FILE
    :param directory: spearmint_directory
    :param f: function to apply to every line (every tuple) of the file
    :return: None
    """

    with open(os.path.join(directory, RESULT_FILE), 'r') as resfile:
        for line in resfile.readlines():
            values = line.split()
            if len(values) < 3:
                continue
            y = values.pop(0)
            dur = values.pop(0)
            x = values
            f(y, dur, x, line)


def run_one_evaluation(directory: str, params: Dict[float, List[float]]) -> None:
    """
    This function is called by MLPOCTask.__update_spearmint_state with new results from provider
    It then simply saves the results to RESULT_FILE file (replaces old line with these hyperparams
    and without score with new one, containing score and DEFAULT_EVAL_TIME
    :param directory: spearmint directory
    :param params: dict of score -> hyperparameters, but since we need the reverse dict, we are reversing it here
    :return: None
    """

    params = {tuple(str(x) for x in v): k for k, v in sorted(params.items())}
    print("Evaluation...")
    newlines = []

    def f(y, dur, x, line):
        X = [float(a) for a in x]
        if dur == 'P' and tuple(X) in params:
            val = params[X]
            newlines.append("{} {} {}\n".format(val, DEFAULT_EVAL_TIME, " ".join(str(p) for p in X)))
        else:
            newlines.append(line)

    process_lines(directory, f)
    with open(os.path.join(directory, RESULT_FILE), 'w') as outfile:
        outfile.writelines(newlines)


def create_conf(directory: str):
    conf = OrderedDict([("HIDDEN_LAYER_SIZE", {"name": "HIDDEN_LAYER_SIZE",
                              "type": "int",
                              "min": 1,
                              "max": 10**5,
                              "size": 1
                              })])
    with open(os.path.join(directory, CONFIG), "w+") as f:
        json.dump(conf, f)


def clean_res(directory):
    global dirties
    dirties = set()
    for f in os.listdir(directory):
        shutil.rmtree(os.path.join(f, directory), ignore_errors=True)


def extract_results(directory: str) -> Tuple[List[str], List[List[str]]]:
    """
    Extracts results from RESULT_FILE, in the form of
    :param directory: spearmint_directory
    :return: [list of results], [list of hyperparameters]
    """
    xs = []
    ys = []

    def f(y, dur, x, _):
        if dur == 'P':
            return
        else:
            xs.append(x)
            ys.append(y)

    process_lines(directory, f)
    return xs, ys


def get_next_configuration(directory: str) -> Optional[List[str]]:
    xs = None

    def f(y, dur, x, _):
        nonlocal xs
        if dur == 'P' and x not in dirties:
            if not xs:
                # we only need to return one new hyperparams configuration
                dirties.add(x)
                xs = x

    process_lines(directory, f)
    return xs