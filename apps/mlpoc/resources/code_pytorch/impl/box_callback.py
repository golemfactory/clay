import json
import os
import time

from messages import MLPOCBlackBoxAskMessage
from params import MESSAGES_OUT_DIR, MESSAGES_IN_DIR

from .box import BlackBox


class BlackBoxFileCallback(BlackBox):
    """After every batch, check if BlackBox decided
    to save the model, and if that's the case, save
    it in the filename location
    """

    def decide(self, hash: str, number_of_epoch) -> bool:
        out_message_path = os.path.join(MESSAGES_OUT_DIR, hash[:8])
        msg = MLPOCBlackBoxAskMessage.new_message(hash,
                                                  number_of_epoch)
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
                    # FIXME debug why sometimes messages received are not valid
                    # but next ones are ok, so the program should not panic
                    print("JSONDecodeError in file " + in_message_path)
                    print("Error: " + str(e))
                    continue
                os.remove(in_message_path)

                assert response["message_type"] == "MLPOCBlackBoxAnswerMessage"

                decision = response["decision"]
                return decision
