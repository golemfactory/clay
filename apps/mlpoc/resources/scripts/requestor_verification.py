import imp
import itertools
import os

import numpy as np
import params


def compare_weights(model1: 'Model', model2: 'Model'):
    weights1 = model1.net.parameters()
    weights2 = model2.net.parameters()

    for x, y in zip(weights1, weights2):
        assert (np.equal(x.data.numpy(), y.data.numpy()).all())


def _hash_from_name(filepath: str):
    name = os.path.basename(filepath)
    return name.split(".")[0]


# def check_batch_hash(data, name):
#     hash = _get_hash_from_name(name)
#     return ... == hash


def find_file_with_ext(ext, dir):
    for file in os.listdir(dir):
        if file.split(".")[-1] == ext:
            return os.path.join(dir, file)

    raise Exception("In dir {} no file with ext {}".format(dir, ext))


if __name__ == "__main__":

    code_file = os.path.join(params.RESOURCES_DIR, "code", "impl")
    impl = imp.load_source("code", code_file)

    equals = []
    serializer = impl.model.ModelSerializer

    for checkpointdir in os.listdir(params.RESOURCES_DIR):
        # loading models
        path = os.path.join(params.RESOURCES_DIR, checkpointdir)
        startmodel_name, endmodel_name = [find_file_with_ext(ext, path)
                                          for ext in ["begin", "end"]]

        startmodel = serializer.load(startmodel_name)
        endmodel = serializer.load(endmodel_name)

        # hashes checking
        assert (str(serializer.get_model_hash(startmodel)) == _hash_from_name(startmodel_name))
        assert (str(serializer.get_model_hash(endmodel)) == _hash_from_name(endmodel_name))

        batch_manager = impl.batchmanager.IrisBatchManager(params.data_file)

        # one epoch of training
        for i, (x, y) in enumerate(
                itertools.islice(batch_manager, params.STEPS_PER_EPOCH)):
            startmodel.run_one_batch(x, y)

        # weights checking
        compare_weights(startmodel, endmodel)

        # print(utils.bcolors.BOLD + utils.bcolors.OKGREEN + "All test passed" + utils.bcolors.ENDC)