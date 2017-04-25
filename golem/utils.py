import logging
import socket
import sys


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
        if sys.platform == "win32" and isinstance(self.msg, unicode):
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
        if not isinstance(s, unicode):
            s = s.decode('utf-8', 'replace')
        return s
