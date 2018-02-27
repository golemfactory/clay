import binascii
import logging
import socket
import sys

import semantic_version

from ethereum.utils import sha3

logger = logging.getLogger(__name__)


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
    raise TypeError(f'Value {s} must be an instance of str or bytes: {type(s)}')


def encode_hex(b):
    if isinstance(b, str):
        b = bytes(b, 'utf-8')
    if isinstance(b, (bytes, bytearray)):
        if b[0] == b'0' and b[1] == b'x':
            b = b[2:]
        return str(binascii.hexlify(b), 'utf-8')
    raise TypeError('Value must be an instance of str or bytes')


def pubkeytoaddr(pubkey: str) -> str:
    return '0x' + encode_hex(sha3(decode_hex(pubkey))[12:])


def tee_target(prefix, proc, input_stream, path, stream):
    """tee emulation for use with threading

    First stream is open to a file pointed by `path`
    Second stream is `stream` arg.
    """

    # Using unix `tee` or powershell.exe `Tee-Object` causes problems with
    # error codes etc. Probably could be solved by bash's `set -o pipefail`
    # but emulating tee functionality in a thread seems to raise less porta-
    # bility issues.
    with open(path, 'a') as log_f:
        while proc.poll() is None:
            line = input_stream.readline(256)
            if line:
                line = line.decode('utf-8', 'replace')
                if not line.endswith('\n'):
                    line += '\n'
                stream.write(prefix + line)
                log_f.write(prefix + line)


def get_version_spec(ours_v: semantic_version.Version) \
        -> semantic_version.Spec:
    spec_str = '>={major}.{minor}.0,<{next_minor}'.format(
        major=ours_v.major,
        minor=ours_v.minor,
        next_minor=ours_v.next_minor(),
    )
    spec = semantic_version.Spec(spec_str)
    return spec


def is_version_compatible(theirs: str,
                          spec: semantic_version.Spec) -> bool:
    try:
        theirs_v = semantic_version.Version(theirs)
    except ValueError as e:
        logger.debug("Can't parse version: %r -> %s", theirs, e)
        return False
    return theirs_v in spec
