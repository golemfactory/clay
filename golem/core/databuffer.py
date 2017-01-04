import struct

from variables import LONG_STANDARD_SIZE

MAX_BUFFER_SIZE = 2 * 1024 * 1024


class DataBuffer:
    """ Data buffer that helps with network communication. """
    def __init__(self):
        """ Create new data buffer """
        self.buffered_data = ""

    def append_ulong(self, num):
        """
        Append given number to data buffer written as unsigned long in network order
        :param long num: number to append (must be higher than 0)
        """
        if num < 0:
            raise AttributeError("num must be grater than 0")
        str_num_rep = struct.pack("!L", num)
        self.buffered_data = "".join([self.buffered_data, str_num_rep])
        return str_num_rep

    def append_string(self, data, check_size=True, overflow_prefix=None):
        """ Append given string to data buffer
        :param check_size: keep buffer size below MAX_BUFFER_SIZE
        :param overflow_prefix: string to prepend on overflow
        :param str data: string to append
        """
        new_size = self.data_size() + len(data)
        if check_size and new_size > MAX_BUFFER_SIZE:
            self.buffered_data = "".join([overflow_prefix or '', data])
        else:
            self.buffered_data = "".join([self.buffered_data, data])

    def data_size(self):
        """ Return size of data in buffer
        :return int: size of data in buffer
        """
        return len(self.buffered_data)

    def peek_ulong(self):
        """ Check long number that is located at the beginning of this data buffer
        :return long: number at the beginning of the buffer
        """
        if len(self.buffered_data) < LONG_STANDARD_SIZE:
            raise ValueError("buffer_data is shorter than {}".format(LONG_STANDARD_SIZE))

        (ret_val,) = struct.unpack("!L", self.buffered_data[0:LONG_STANDARD_SIZE])
        return ret_val

    def read_ulong(self):
        """ Remove long number at the beginning of this data buffer and return it.
        :return long: long number removed from the beginning of buffer
        """
        val_ = self.peek_ulong()
        self.buffered_data = self.buffered_data[4:]

        return val_

    def peek_string(self, num_chars):
        """ Return first <num_chars> chars from buffer. Doesn't change the buffer.
        :param long num_chars: how many chars should be read from buffer
        :return str: first <num_chars> chars from buffer
        """
        if num_chars > len(self.buffered_data):
            raise AttributeError("num_chars is grater than buffer length")

        ret_str = self.buffered_data[:num_chars]
        return ret_str

    def read_string(self, num_chars):
        """ Remove first <num_chars> chars from buffer and return them.
        :param long num_chars: how many chars should be read and removed from buffer
        :return str: string removed form buffer
        """
        val_ = self.peek_string(num_chars)
        self.buffered_data = self.buffered_data[num_chars:]

        return val_

    def read_all(self):
        """ Return all data from buffer and clear the buffer.
        :return str: all data that was in the buffer.
        """
        ret_data = self.buffered_data
        self.buffered_data = ""

        return ret_data

    def read_len_prefixed_string(self):
        """ Read long number from the buffer and then read string with that length from the buffer
        :return str: first string from the buffer (after long)
        """
        ret_str = None

        if (self.data_size() > LONG_STANDARD_SIZE and
                self.data_size() >= (self.peek_ulong() + LONG_STANDARD_SIZE)):
            num_chars = self.read_ulong()
            ret_str = self.read_string(num_chars)

        return ret_str

    def get_len_prefixed_string(self):
        """Generator function that return from buffer strings preceded with their length (long) """
        while (self.data_size() > LONG_STANDARD_SIZE and
               self.data_size() >= (self.peek_ulong() + LONG_STANDARD_SIZE)):
            num_chars = self.read_ulong()
            yield self.read_string(num_chars)

    def append_len_prefixed_string(self, data):
        """ Append length of a given data and then given data to the buffer
        :param str data: data to append
        """
        prefix = self.append_ulong(len(data))
        self.append_string(data, overflow_prefix=prefix)

    def clear_buffer(self):
        """ Remove all data from the buffer """
        self.buffered_data = ""
