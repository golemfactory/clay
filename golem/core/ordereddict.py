from collections import OrderedDict


class SizedOrderedDict(OrderedDict):

    def __init__(self, max_len, **kwds):
        self.__max_len = max_len
        super(SizedOrderedDict, self).__init__(**kwds)

    def __setitem__(self, key, value, **_):
        if self.__max_len and len(self) == self.__max_len:
            self.popitem(last=False)  # FIFO
        OrderedDict.__setitem__(self, key, value)
