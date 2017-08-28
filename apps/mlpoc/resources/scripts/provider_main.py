# TODO Here is be the provider_main.py script which is initializing everyting
# and running the training

import params

from .impl import model


def run():
    runner = model.ModelRunner(params.OUTPUT_DIR,
                               probability=1,
                               verbose=0)

    runner.run_full_training()


run()
