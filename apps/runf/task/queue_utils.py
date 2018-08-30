# some code based on braninpy from
# https://github.com/JasperSnoek/spearmint/blob/master/spearmint-lite/braninpy/braninrunner.py  # noqa

import json
import logging
import os
import shutil
import tempfile
import time
from collections import OrderedDict
from typing import Tuple, List, Optional, Dict, Callable

logger = logging.getLogger("apps.mlpoc")


# busy loop will wait this much between subsequent checks
# if results already arrived
UPDATE_PERIOD = 0.1

# dirty-state hyperparams configurations
# (so these which were already send to provider
# but there is still no answer)
dirties = set()


def run_one_evaluation(directory: str, params: Dict[str, List[str]]) -> None:
    """
    This function is called by MLPOCTask.__update_spearmint_state
    with new results from provider. It then simply saves the results
    to RESULT_FILE file (replaces old line with, containing these hyperparams
    without score with new one, containing score and DEFAULT_EVAL_TIME
    :param directory: spearmint directory
    :param params: dict of score -> hyperparameters (but since we need
           the reverse dict, we are reversing it below)
    :return: None
    """

    params = {tuple(x for x in v): k for k, v in sorted(params.items())}
    logger.info("Running spearmint update")
    newlines = []

    def f(y, dur, x, line):
        if dur == 'P' and tuple(x) in params:
            val = params[tuple(x)]
            newlines.append("{} {} {}\n".format(val,
                                                DEFAULT_EVAL_TIME,
                                                " ".join(x)))
        else:
            newlines.append(line)

    process_lines(directory, f)

    # this is an atomic write
    # inspired by http://stupidpythonideas.blogspot.com/2014/07/getting-atomic-writes-right.html  # noqa
    with tempfile.NamedTemporaryFile("w", dir=directory, delete=False) as fout:
        fout.writelines(newlines)
    os.replace(fout.name, os.path.join(directory, RESULT_FILE))


def create_conf(directory: str):
    # TODO this config should be constructed dynamically
    # or just read from user input

    # important note - it has to be OrderedDict, the order is important
    conf = OrderedDict([
        ("HIDDEN_LAYER_SIZE", {
            "name": "HIDDEN_LAYER_SIZE",
            "type": "int",
            "min": 1,
            "max": 10 ** 5,
            "size": 1
        })])

    with open(os.path.join(directory, CONFIG), "w") as f:
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


def generate_new_suggestions(file):
    open(file, "w").close()  # create signal file
    while os.path.exists(file):
        # wait till the suggestions are filled in and the file is deleted
        time.sleep(UPDATE_PERIOD)
