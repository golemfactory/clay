# TODO Here is be the provider_main.py script which is initializing everyting
# and running the training

# these things have to be dynamically loaded
# from code path
# from impl import config
# from impl.model import ModelRunner


runner = ModelRunner(config.SHARED_PATH,
                     probability=1,
                     verbose=0,
                     save_model_as_dict=config.SAVE_MODEL_AS_DICT)

runner.run_full_training()
