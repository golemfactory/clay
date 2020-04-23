import struct

from .variables import LONG_STANDARD_SIZE


class DataBuffer:
    """ Data buffer that helps with network communication. """
    def __init__(self):
        """ Create new data buffer """
        self.buffered_data = b""

    def append_ulong(self, num):
        """
        Append given number to data buffer written as unsigned long
        in network order
        :param long num: number to append (must be higher than 0)
        """
        if num < 0:
            raise AttributeError("num must be grater than 0")
        bytes_num_rep = struct.pack("!L", num)
        self.buffered_data += bytes_num_rep
        return bytes_num_rep

    def append_bytes(self, data):
        """ Append given bytes to data buffer
        :param bytes data: bytes to append
        """
        self.buffered_data += data

    def data_size(self):
        """ Return size of data in buffer
        :return int: size of data in buffer
        """
        return len(self.buffered_data)

    def peek_ulong(self):
        """
        Check long number that is located at the beginning of this data buffer
        :return (long|None): number at the beginning of the buffer if it's there
        """
        if len(self.buffered_data) < LONG_STANDARD_SIZE:
            return None

        (ret_val,) = \
            struct.unpack("!L", self.buffered_data[0:LONG_STANDARD_SIZE])
        return ret_val

    def read_ulong(self):
        """
        Remove long number at the beginning of this data buffer and return it.
        :return long: long number removed from the beginning of buffer
        """
        val_ = self.peek_ulong()
        if val_ is None:
            raise ValueError(
                "buffer_data is shorter than {}".format(LONG_STANDARD_SIZE))
        self.buffered_data = self.buffered_data[LONG_STANDARD_SIZE:]

        return val_

    def peek_bytes(self, num_bytes):
        """
        Return first <num_bytes> bytes from buffer. Doesn't change the buffer.
        :param long num_bytes: how many bytes should be read from buffer
        :return bytes: first <num_bytes> bytes from buffer
        """
        if num_bytes > len(self.buffered_data):
            raise AttributeError("num_bytes is grater than buffer length")

        ret_bytes = self.buffered_data[:num_bytes]
        return ret_bytes

    def read_bytes(self, num_bytes):
        """
        Remove first <num_bytes> bytes from buffer and return them.
        :param long num_bytes: how many bytes should be read and removed
         from buffer
        :return bytes: bytes removed form buffer
        """
        val_ = self.peek_bytes(num_bytes)
        self.buffered_data = self.buffered_data[num_bytes:]

        return val_

    def read_all(self):
        """
        Return all data from buffer and clear the buffer.
        :return bytes: all data that was in the buffer.
        """
        ret_data = self.buffered_data
        self.buffered_data = b""

        return ret_data

    def read_len_prefixed_bytes(self):
        """
        Read long number from the buffer and then read bytes with that length
        from the buffer
        :return bytes: first bytes from the buffer (after long)
        """
        ret_bytes = None

        if (self.data_size() >= LONG_STANDARD_SIZE and
                self.data_size() >= (self.peek_ulong() + LONG_STANDARD_SIZE)):
            num_bytes = self.read_ulong()
            ret_bytes = self.read_bytes(num_bytes)

        return ret_bytes

    def get_len_prefixed_bytes(self):
        """
        Generator function that return from buffer datas preceded with
        their length (long)
        """
        while (self.data_size() > LONG_STANDARD_SIZE and
               self.data_size() >= (self.peek_ulong() + LONG_STANDARD_SIZE)):
            num_bytes = self.read_ulong()
            yield self.read_bytes(num_bytes)

    def append_len_prefixed_bytes(self, data):
        """
        Append length of a given data and then given data to the buffer
        :param bytes data: data to append
        """
        self.append_ulong(len(data))
        self.append_bytes(data)

    def clear_buffer(self):
        """ Remove all data from the buffer """
        self.buffered_data = b""
