import os
from golem.core.simpleenv import _get_local_datadir


def get_save_dir():
    save_dir = _get_local_datadir("save")
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    return save_dir
