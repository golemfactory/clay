import os
import random as rn

import numpy as np
import torch

from .config import SEED


# TODO update derandom to take random seeds input stream
def derandom(*args, **kwargs):
    os.environ['PYTHONHASHSEED'] = str(SEED)
    np.random.seed(SEED)
    rn.seed(SEED)
    torch.manual_seed(7)
