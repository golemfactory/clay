import struct
from _pysha3 import sha3_256

import rlp
from devp2p.protocol import BaseProtocol
from rlp import sedes

from golem.core.common import get_timestamp_utc

TIME_WND = 10.  # s
HALF_TIME_WND = TIME_WND / 2.


def digest(payload, ts):
    h = sha3_256()
    h.update(payload)
    h.update(struct.pack('Q', ts))  # unsigned 8-byte int
    return h.digest()


class signed(BaseProtocol.command):

    structure = [
        ('payload', rlp.sedes.binary),
        ('ts', rlp.sedes.big_endian_int),
        ('sig', rlp.sedes.binary)
    ]


class SigningProtocol(BaseProtocol):

    def __init__(self, peer, service):
        assert hasattr(service, 'task_server')
        super().__init__(peer, service)
        self._keys_auth = service.task_server.keys_auth

    def sign(self, data):
        return self._keys_auth.sign(data)

    def verify(self, sig, data):
        pubkey = self.peer.remote_pubkey
        return self._keys_auth.verify(sig, data, pubkey)

    class command(BaseProtocol.command):

        def create(self, proto, *args, **kwargs):
            message = super().create(proto, *args, **kwargs)
            payload = super().encode_payload(message)
            ts = int(get_timestamp_utc() * 10 ** 6)
            sig = proto.sign(digest(payload, ts))
            return payload, ts, sig

        def receive(self, proto, data):
            payload, ts, sig = data['payload'], data['ts'], data['sig']
            self.verify_message(proto, payload, ts, sig)

            decoded = super().decode_payload(data['payload'])
            decoded = self.received(decoded)

            for cb in self.receive_callbacks:
                if isinstance(self.structure, sedes.CountableList):
                    cb(proto, decoded, _msg_bytes=data)
                else:
                    cb(proto, **decoded, _msg_bytes=data)

        def received(self, decoded):
            """
            Message handler for post-processing
            :param decoded: Decoded message
            :return: (optionally) altered decoded message
            """
            return decoded

        @classmethod
        def encode_payload(cls, data):
            return signed.encode_payload(data)

        @classmethod
        def decode_payload(cls, rlp_data):
            return signed.decode_payload(rlp_data)

        @classmethod
        def verify_message(cls, proto, payload, ts, sig):
            payload_digest = digest(payload, ts)
            if not proto.verify(sig, payload_digest):
                raise AssertionError('Invalid message signature')

            ts /= 10 ** 6  # scale down (serialization)
            now = get_timestamp_utc()

            before, after = now - HALF_TIME_WND, now + HALF_TIME_WND
            if not (before <= ts <= after):
                raise AssertionError('Time out of sync')
