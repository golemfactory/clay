import struct


class LabeledMessage:

    _FMT = 'h'
    _SZ = struct.calcsize(_FMT)

    def __init__(self, label: int, data: bytes) -> None:
        self.label = label
        self.data = data

    def pack(self) -> bytes:
        label = struct.pack(self._FMT, self.label)
        return label + self.data

    @classmethod
    def unpack(cls, blob: bytes) -> 'LabeledMessage':
        if len(blob) <= cls._SZ:
            raise ValueError("Received an empty message: %r", blob[cls._SZ:])

        label = struct.unpack(cls._FMT, blob[:cls._SZ])[0]
        blob = blob[cls._SZ:]

        return LabeledMessage(label, blob)
