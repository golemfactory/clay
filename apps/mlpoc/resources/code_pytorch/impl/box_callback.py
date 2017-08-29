import json
import os
import time

from .box import BlackBox
from .hash import Hash
from ..messages import (MLPOCBlackBoxAskMessage)
from ..params import MESSAGES_OUT_PATH, MESSAGES_IN_PATH


class BlackBoxFileCallback(BlackBox):
    """After every batch, check if BlackBox decided
    to save the model, and if that's the case, save
    it in the filename location
    """

    def decide(self, hash: Hash) -> bool:
        out_message_path = os.path.join(MESSAGES_OUT_PATH, str(hash)[:8])
        # TODO 1: change epoch num,
        msg = MLPOCBlackBoxAskMessage.new_message(str(hash), number_of_epoch=0)
        with open(out_message_path, "w") as f:
            json.dump(msg, f)

        while True:
            time.sleep(0.1)
            ls = os.listdir(MESSAGES_IN_PATH)
            if ls:
                in_message_path = os.path.join(MESSAGES_IN_PATH, ls[0])
                with open(in_message_path, "r") as f:
                    response = json.load(f)

                os.remove(in_message_path)
                # Do some more authentication here!!
                # like checking signature or something
                assert msg["message_type"] == "MLPOCBlackBoxAnswerMessage"

                decision = msg["decision"]
                return decision
