import logging
import socket


def find_free_net_port():
    """Finds a free port on the host"""
    s = socket.socket()
    s.bind(('', 0))            # Bind to a free port provided by the host.
    return s.getsockname()[1]  # Return the port assigned.


class UnicodeFormatter(logging.Formatter):
    """This formatter is a workaround for a bug in logging module which causes
    problems when logging bytestrings with special characters.
    SEE: tests.test_logging.TestLogging.test_unicode_formatter
    """
    def format(self, *args, **kwargs):
        s = super(UnicodeFormatter, self).format(*args, **kwargs)
        if not isinstance(s, unicode):
            s = s.decode('utf-8', 'replace')
        return s
