import os
import random as rn

import numpy as np
import torch

# TODO update derandom to take random seeds input stream
def derandom(*args, **kwargs):
    os.environ['PYTHONHASHSEED'] = '0'
    np.random.seed(7)
    rn.seed(7)
    torch.manual_seed(7)

# from blender build tools
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'