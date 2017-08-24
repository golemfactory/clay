# TODO Here is be the provider_main.py script which is initializing everyting
# and running the training

# these things have to be dynamically loaded
# from code path
# from impl import config
# from impl.model import ModelRunner
import imp
import os

import params


def run():
    code_file = os.path.join(params.RESOURCES_DIR, "code", "model.py")
    model = imp.load_source("code", code_file)

    runner = model.ModelRunner(params.OUTPUT_DIR,
                               probability=1,
                               verbose=0)

    runner.run_full_training()


run()
