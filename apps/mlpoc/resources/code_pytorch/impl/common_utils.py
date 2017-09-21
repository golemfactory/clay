# copied from Blender build tools
import os
from collections import namedtuple


class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# these two functions are inversions of each other

def name_of_model_dump(epoch, hash, ext):
    return "{}-{}.{}".format(epoch, hash, ext)


Details = namedtuple("Details", ["epoch", "hash", "ext"])


def details_from_dump_name(name):
    name = os.path.basename(name)
    name, ext = os.path.splitext(name)
    epoch, hash = name.split("-")
    return Details(epoch=epoch,
                   hash=hash,
                   ext=ext)
