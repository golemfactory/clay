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
        out_message_path = os.path.join(MESSAGES_OUT_DIR, str(hash)[:8])
        # TODO 1: change epoch num,
        msg = MLPOCBlackBoxAskMessage.new_message(str(hash), number_of_epoch=0)
        with open(out_message_path, "w") as f:
            json.dump(msg, f)

        while True:
            time.sleep(0.1)
            ls = os.listdir(MESSAGES_IN_DIR)
            if ls:
                in_message_path = os.path.join(MESSAGES_IN_DIR, ls[0])
                try:
                    with open(in_message_path, "r") as f:
                        response = json.load(f)
                except json.JSONDecodeError as e:
                    # TODO very ugly, do something about it - but what?
                    print("JSONDecodeError in file " + in_message_path)
                    print("Error: " + str(e))
                    continue
                os.remove(in_message_path)
                # Do some more authentication here!!
                # like checking signature or something
                assert response["message_type"] == "MLPOCBlackBoxAnswerMessage"

                decision = response["decision"]
                return decision
