import torch
from keras.callbacks import Callback
from impl.utils import derandom
import os

from impl.box import BlackBox
from impl.hash import Hash
from impl.batchmanager import BatchManager


class BlackBoxCallback():
    """After every batch, check if BlackBox decided
    to save the model, and if that's the case, save
    it in the filename location
    """
    pass