# this class is a replacement for normal BlackBoxCallback
# it is used for tests, as mock
import json
import os
import time

from .box import BlackBox
from .hash import Hash
from messages import MLPOCBlackBoxAskMessage
from params import MESSAGES_OUT_DIR, MESSAGES_IN_DIR



class BlackBoxFileCallback(BlackBox):
    """After every batch, check if BlackBox decided
    to save the model, and if that's the case, save
    it in the filename location
    """

    def decide(self, hash: Hash) -> bool:
        return True
