import imp
import os

import params


def run():
    code_file = os.path.join(params.RESOURCES_DIR, "code", "impl")
    impl = imp.load_source("code", code_file)

    runner = impl.model.HonestModelRunner(params.OUTPUT_DIR, params.data_file)

    runner.run_full_training()


run()
