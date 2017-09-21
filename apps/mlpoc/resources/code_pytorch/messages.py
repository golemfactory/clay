import abc


class SubtaskPRMessage(metaclass=abc.ABCMeta):
    @staticmethod
    @abc.abstractmethod
    def new_message(*args, **kwargs):
        pass


class MLPOCBlackBoxAskMessage(SubtaskPRMessage):
    @staticmethod
    def new_message(params_hash: str, number_of_epoch: int):
        return {"message_type": "MLPOCBlackBoxAskMessage",
                "params_hash": params_hash,
                "number_of_epoch": number_of_epoch
                }


class MLPOCBlackBoxAnswerMessage(SubtaskPRMessage):
    @staticmethod
    def new_message(decision: bool):
        return {"message_type": "MLPOCBlackBoxAnswerMessage",
                "decision": decision
                }
