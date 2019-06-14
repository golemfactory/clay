import inspect
import sys

from abc import ABCMeta
from typing import Dict, List, Tuple, Type, Union, Optional

__all__ = (
    'Event',
    'Listening',
    'Terminated',
    'Connected',
    'Disconnected',
    'Message',
    'Clogged',
    'Error',
)


class _IntConvertMixin:

    @classmethod
    def convert_from(cls, value: int):
        return cls(value)

    def convert_to(self) -> int:
        return int(self.value)


class Event(metaclass=ABCMeta):
    ID = None
    __events = None

    @classmethod
    def convert_from(
        cls,
        payload: Union[List, Tuple, None]
    ) -> Optional['Event']:

        if not payload:
            return
        if len(payload) < 1:
            raise ValueError("Event ID is missing")

        if not cls.__events:
            cls.__events = _subclasses(cls)

        event = cls.__events.get(payload[0])
        return event(*payload[1:])


class PeerEvent(Event, metaclass=ABCMeta):

    def __init__(self, peer_id: str) -> None:
        self.peer_id = peer_id


class PeerEndpointEvent(PeerEvent, metaclass=ABCMeta):

    def __init__(self, peer_id: str, endpoint: Tuple) -> None:
        super().__init__(peer_id)
        self.endpoint = Endpoint(endpoint)


class Listening(Event):
    ID = 10

    def __init__(self, addresses: List[Tuple[str, int]]) -> None:
        self.addresses = addresses
        self.address = next(iter(addresses))


class Terminated(Event):
    ID = 11


class Connected(PeerEndpointEvent):
    ID = 100

    def __init__(
        self,
        peer_id: str,
        endpoint: Tuple,
        peer_pubkey: bytes,
    ) -> None:
        super().__init__(peer_id, endpoint)
        self.peer_pubkey = peer_pubkey


class Disconnected(PeerEndpointEvent):
    ID = 110


class Message(PeerEvent):
    ID = 200

    def __init__(
        self,
        peer_id: str,
        connected_point: Tuple,
        user_message: Tuple[bytes, bytes],
    ) -> None:
        super().__init__(peer_id)
        self.endpoint = Endpoint(connected_point)
        self.protocol_id, self.blob = user_message


class Clogged(PeerEvent):
    ID = 300


class Error(Event):
    ID = 400

    def __init__(self, error) -> None:
        self.error = error


class Endpoint(_IntConvertMixin):
    Outgoing = 0
    Incoming = 1

    def __init__(self, endpoint: Union[List, Tuple]) -> None:
        self.initiator = endpoint[0] == self.Outgoing
        self.address = endpoint[1]
        self.address_local = endpoint[2]


def _subclasses(cls) -> Dict[str, Type]:
    module = sys.modules[__name__]
    events = inspect.getmembers(
        module,
        lambda c: bool(
            inspect.isclass(c) and
            c is not cls and
            issubclass(c, cls)
        )
    )
    return {e.ID: e for _, e in events}
