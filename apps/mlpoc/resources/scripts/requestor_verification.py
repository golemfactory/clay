import itertools
import os
import sys

import numpy as np
import params

sys.path.append(os.path.join(params.RESOURCES_DIR, "code", "impl"))
sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))

from impl import (model,
                  batchmanager,
                  config,
                  common_utils)
from impl.hash import StateHash
from impl.model import ComputationState
from impl.common_utils import details_from_dump_name


def compare_weights(model1: 'Model', model2: 'Model'):
    weights1 = model1.net.parameters()
    weights2 = model2.net.parameters()

    for x, y in zip(weights1, weights2):
        # not equal here can be replacd by np.isclose
        if not np.equal(x.data.numpy(), y.data.numpy()).all():
            return False
    return True


def _hash_from_name(filepath: str):
    return details_from_dump_name(filepath).hash


# TODO issue https://github.com/imapp-pl/golem_rd/issues/122
# def check_batch_hash(data, name):
#     hash = _get_hash_from_name(name)
#     return ... == hash


# impossible to do if we're doing cross-validation
# def check_score(data, name):
#     """Check if the score in results file matches real score
#     of the network
#     """
#     pass


# duplication of golem.core.fileshelper.find_file_with_ext
def find_file_with_ext(ext, dir):
    for file in os.listdir(dir):
        if file.split(".")[-1] == ext:
            return os.path.join(dir, file)

    raise Exception("In dir {} no file with ext {}".format(dir, ext))


def run():
    serializer = model.ModelSerializer
    black_box_history = dict(params.black_box_history)

    data_file = os.path.join(params.RESOURCES_DIR, "data", params.data_file)
    checkpoints_place = os.path.join(params.RESOURCES_DIR, "checkpoints")
    for checkpointdir in os.listdir(checkpoints_place):

        # checkpointdir is named after the epoch during which it was created
        epoch = int(checkpointdir)

        # loading models
        path = os.path.join(checkpoints_place, checkpointdir)
        startmodel_name, endmodel_name = [find_file_with_ext(ext, path)
                                          for ext in ["begin", "end"]]

        startmodel = serializer.load(startmodel_name)
        endmodel = serializer.load(endmodel_name)

        # hashes checking
        startmodel_hash = str(startmodel.get_hash())
        endmodel_hash = str(endmodel.get_hash())

        if epoch not in black_box_history:
            raise Exception("No hashes for the epoch {}".format(epoch))

        if not startmodel_hash == _hash_from_name(startmodel_name):
            raise Exception("Hash of startmodel from name {} "
                            "not equal to real hash {}".format(
                startmodel_hash,
                _hash_from_name(startmodel_name)
            ))

        if not endmodel_hash == _hash_from_name(endmodel_name):
            raise Exception("Hash of endmodel from name {} "
                            "not equal to real hash {}".format(
                endmodel_hash,
                _hash_from_name(endmodel_name)
            ))

        boxed_hash = black_box_history[epoch]
        real_state_hash = str(StateHash(ComputationState(startmodel,
                                                         endmodel)))
        if not real_state_hash == boxed_hash:
            raise Exception("Real hash of state transition {} "
                            "not equal to the hash saved in the box {}".format(
                real_state_hash,
                boxed_hash
            ))

        batch_manager = batchmanager.IrisBatchManager(data_file)

        # one epoch of training
        for i, (x, y) in enumerate(itertools.islice(batch_manager,
                                                    config.STEPS_PER_EPOCH)):
            startmodel.run_one_batch(x, y)

        # weights checking
        if not compare_weights(startmodel, endmodel):
            raise Exception("Not equal weights")

        print("{}{}{}{}".format(common_utils.bcolors.BOLD,
                                common_utils.bcolors.OKGREEN,
                                "All test passed",
                                common_utils.bcolors.ENDC))
        return True


run()
