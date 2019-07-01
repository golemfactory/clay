import logging
import socket

import semantic_version

from eth_utils import decode_hex, encode_hex, to_checksum_address
from ethereum.utils import sha3, privtoaddr as _privtoaddr

logger = logging.getLogger(__name__)


def find_free_net_port():
    """Finds a free port on the host"""
    s = socket.socket()
    s.bind(('', 0))            # Bind to a free port provided by the host.
    return s.getsockname()[1]  # Return the port assigned.


def privkeytoaddr(privkey: bytes) -> str:
    """
    Converts a private key bytes sequence to a string, representing the
    hex-encoded ethereum address with checksum
    :raises ValueError: provided bytes sequence is not an ethereum private key
    """
    try:
        return to_checksum_address(encode_hex(_privtoaddr(privkey)))
    except AssertionError:
        raise ValueError("not a valid private key")


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


def get_min_version(ours_v: semantic_version.Version) \
        -> semantic_version.Version:
    min_version = semantic_version.Version(str(ours_v))  # copy
    min_version.patch = 0
    min_version.prerelease = ()
    min_version.build = ()
    return min_version
