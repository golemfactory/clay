import logging
import socket
import sys
import collections

import binascii


def find_free_net_port():
    """Finds a free port on the host"""
    s = socket.socket()
    s.bind(('', 0))            # Bind to a free port provided by the host.
    return s.getsockname()[1]  # Return the port assigned.


class UnicodeRecord(logging.LogRecord):
    ENCODING = 'utf-8'

    @classmethod
    def from_record(cls, record):
        # based on logging.makeLogRecord
        u_record = cls(None, None, "", 0, "", (), None, None)
        u_record.__dict__.update(record.__dict__)
        return u_record

    def getMessage(self):
        if sys.platform == "win32" and isinstance(self.msg, str):
            self.msg = self.msg.encode(self.ENCODING, 'replace')
        return super(UnicodeRecord, self).getMessage()


class UnicodeFormatter(logging.Formatter):
    """This formatter is a workaround for a bug in logging module which causes
    problems when logging bytestrings with special characters.
    SEE: tests.test_logging.TestLogging.test_unicode_formatter
    """

    def format(self, record):
        u_record = UnicodeRecord.from_record(record)
        s = super(UnicodeFormatter, self).format(u_record)
        if not isinstance(s, str):
            s = s.decode('utf-8', 'replace')
        return s


def decode_hex(s):
    if isinstance(s, str):
        if s.startswith('0x'):
            s = s[2:]
        return bytes.fromhex(s)
    if isinstance(s, (bytes, bytearray)):
        if s[0] == b'0' and s[1] == b'x':
            s = s[2:]
        return binascii.unhexlify(s)
    raise TypeError('Value must be an instance of str or bytes')


def encode_hex(b):
    if isinstance(b, str):
        b = bytes(b, 'utf-8')
    if isinstance(b, (bytes, bytearray)):
        if b[0] == b'0' and b[1] == b'x':
            b = b[2:]
        return str(binascii.hexlify(b), 'utf-8')
    raise TypeError('Value must be an instance of str or bytes')


def tee_target(prefix, proc, path):
    """tee emulation for use with threading"""

    # Using unix `tee` or powershell.exe `Tee-Object` causes problems with
    # error codes etc. Probably could be solved by bash's `set -o pipefail`
    # but emulating tee functionality in a thread seems to raise less porta-
    # bility issues.
    channels = (
        ('out: ', proc.stderr, sys.stderr),
        ('err: ', proc.stdout, sys.stdout),
    )
    with open(path, 'a') as log_f:
        while proc.poll() is None:
            for stream_prefix, in_, out in channels:
                line = in_.readline()
                if line:
                    out.write(prefix + str(line))
                    log_f.write(stream_prefix + str(line))


class OrderedClassMembers(type):
    # Using to get class properties in order
    # In Python v3.6 and above could be solved with iteration on dict
    # @see https://www.python.org/dev/peps/pep-0520/
    # @example
    # def __iter__(self):
    #     for count, (key, value) in enumerate(self.__dict__.items(), 0):
    #         yield count, value

    @classmethod
    def __prepare__(self, name, bases):
        return collections.OrderedDict()

    def __new__(self, name, bases, classdict):
        classdict['__ordered__'] = [
            key for key in classdict.keys()
                if key not in ('__module__', '__qualname__')
            ]
        return type.__new__(self, name, bases, classdict)
