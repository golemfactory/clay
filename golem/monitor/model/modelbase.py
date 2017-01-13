import abc
import time


class ModelBase(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def dict_repr(self):
        """Returns dictionary representation of the current instance"""
        pass


class BasicModel(ModelBase):

    def __init__(self, type_str_repr, cliid, sessid):
        # TODO: use class.TYPE
        self.type = type_str_repr
        self.timestamp = time.time()
        self.cliid = cliid
        self.sessid = sessid

    def dict_repr(self):
        return self.__dict__
