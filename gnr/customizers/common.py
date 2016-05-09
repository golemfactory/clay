import os
from golem.core.simpleenv import get_local_datadir


def get_save_dir():
    save_dir = get_local_datadir("save")
    if not os.path.exists(save_dir):
        os.mkdir(save_dir)
    return save_dir
