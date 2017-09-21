import sys
import itertools
import os

import numpy as np

import params

sys.path.append(os.path.join(params.RESOURCES_DIR, "code", "impl"))
sys.path.append(os.path.join(params.RESOURCES_DIR, "code"))

from impl import model, batchmanager, config, utils
from impl.hash import StateHash
from impl.model import ComputationState

def compare_weights(model1: 'Model', model2: 'Model'):
    weights1 = model1.net.parameters()
    weights2 = model2.net.parameters()

    for x, y in zip(weights1, weights2):
        if not np.equal(x.data.numpy(), y.data.numpy()).all():
            return False
    return True

# TODO write that down somewhere explicite
# That the name of model dump is EpochNum-HashOfState.begin (or .end)
def _hash_from_name(filepath: str):
    name = os.path.basename(filepath)
    return name.split(".")[0].split("-")[1]


# def check_batch_hash(data, name):
#     hash = _get_hash_from_name(name)
#     return ... == hash


# def check_score(data, name):
#     """Check if the score in results file matches real score
#     of the network
#     """
#     pass


def find_file_with_ext(ext, dir):
    for file in os.listdir(dir):
        if file.split(".")[-1] == ext:
            return os.path.join(dir, file)

    raise Exception("In dir {} no file with ext {}".format(dir, ext))


def run():
    serializer = model.ModelSerializer
    black_box_history = dict(params.black_box_history)

    data_file = os.path.join(params.RESOURCES_DIR, "data", params.data_file)
    for checkpointdir in os.listdir(os.path.join(params.RESOURCES_DIR, "checkpoints")):

        epoch = int(checkpointdir)

        # loading models
        path = os.path.join(params.RESOURCES_DIR, "checkpoints", checkpointdir)
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
            raise Exception("Hash of startmodel from name: {} not equal to real hash: {}".format(
                startmodel_hash,
                _hash_from_name(startmodel_name)
            ))

        if not endmodel_hash == _hash_from_name(endmodel_name):
            raise Exception("Hash of endmodel from name: {} not equal to real hash: {}".format(
                endmodel_hash,
                _hash_from_name(endmodel_name)
            ))

        boxed_hash = black_box_history[epoch]
        real_state_hash = str(StateHash(ComputationState(startmodel, endmodel)))
        if not real_state_hash == boxed_hash:
            raise Exception("Real hash of state transition: {} not equal to the hash saved in the box: {}".format(
                real_state_hash,
                boxed_hash
            ))

        batch_manager = batchmanager.IrisBatchManager(data_file)

        # one epoch of training
        for i, (x, y) in enumerate(itertools.islice(batch_manager, config.STEPS_PER_EPOCH)):
            startmodel.run_one_batch(x, y)

        # weights checking
        if not compare_weights(startmodel, endmodel):
            raise Exception("Not equal weights")

        print(utils.bcolors.BOLD + utils.bcolors.OKGREEN + "All test passed" + utils.bcolors.ENDC)
        return True


run()