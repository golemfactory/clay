from typing import List, Tuple, Dict, Union

from golem.network.hyperdrive.client import HyperdriveClientOptions
from golem.resource.client import ClientOptions as ResourceClientOptions
from golem.resource.hyperdrive.resource import Resource as HyperdriveResource

from golem.resource.messages.ttypes import PeerEntry, AddressEntry, \
    ClientOptions, Option, ResourceEntry, PulledEntry, \
    Added, Pulled, Empty, Resources, Resource, Error, PullResource


###
# Message builders
###

def build_pull_resource(request_id: bytes, **kwargs) -> PullResource:
    converted = dict(kwargs)

    if 'entry' in kwargs:
        converted['entry'] = from_py_resource_entry(
            kwargs['entry'])

    if 'client_options' in kwargs:
        converted['client_options'] = from_py_client_options(
            kwargs['client_options'])

    return PullResource(request_id=request_id, **converted)


def build_added(request_id: bytes, result, *_args, **_kwargs) -> Added:
    return Added(request_id=request_id, entry=from_py_resource_entry(result))


def build_pulled(request_id: bytes, result, *_args, **_kwargs) -> Pulled:
    return Pulled(request_id=request_id, entry=from_py_pulled_entry(result))


def build_resources(request_id: bytes, result, *_args, **_kwargs) -> Resources:
    resources = list(map(from_py_resource, result))
    return Resources(request_id=request_id, resources=resources)


def build_empty(request_id: bytes, *_args, **_kwargs) -> Empty:
    return Empty(request_id=request_id)


def build_error(request_id: bytes, message: str) -> Error:
    return Error(request_id=request_id, message=message)

###
# Struct converters
###


def to_py_peer_entry(src: PeerEntry) -> Dict:
    return {
        protocol: (address.host, address.port)
        for protocol, address in src.entries.items()
    }


def from_py_peer_entry(src: Dict) -> PeerEntry:
    return PeerEntry({
        protocol: AddressEntry(host=host, port=port)
        for protocol, (host, port) in src.items()
    })


def to_py_resource(src: Resource) -> HyperdriveResource:
    return HyperdriveResource(**src.__dict__)


def from_py_resource(src: HyperdriveResource) -> Resource:
    return Resource(**src.__dict__)


def to_py_client_options(src: ClientOptions) -> HyperdriveClientOptions:

    client_options = HyperdriveClientOptions(src.client_id, src.version)

    for option in src.options or []:
        if option.timeout is not None:
            client_options.timeout = option.timeout
        if option.peers is not None:
            peers = list(map(to_py_peer_entry, option.peers))
            client_options.peers = peers

    return client_options


def from_py_client_options(src: HyperdriveClientOptions) -> ClientOptions:

    result = ClientOptions(client_id=src.client_id, version=src.version)
    timeout = getattr(src, 'timeout', None)
    peers = getattr(src, 'peers', None)
    size = getattr(src, 'size', None)

    if timeout or peers or size:
        result.options = []

        if timeout:
            result.options.append(Option(timeout=timeout))
        if peers:
            converted = list(map(from_py_peer_entry, peers))
            result.options.append(Option(peers=converted))
        if size:
            result.options.append(Option(size=size))

    return result


def to_py_resource_entry(src: ResourceEntry) -> Tuple[str, List[str]]:
    return src.resource_hash, src.files


def from_py_resource_entry(src: Union[str, Tuple]) -> ResourceEntry:
    if isinstance(src, tuple):
        return ResourceEntry(resource_hash=src[0], files=src[1])
    return ResourceEntry(resource_hash=src, files=[])


def to_py_pulled_entry(src: PulledEntry) -> Tuple[Tuple, List, str]:
    return to_py_resource_entry(src.entry), src.files, src.task_id


def from_py_pulled_entry(src: Tuple[Tuple, List, str]):
    return PulledEntry(entry=from_py_resource_entry(src[0]),
                       files=src[1],
                       task_id=src[2] if len(src) > 2 else None)

###
# Struct to converter mappings
###


TO_PYTHON_CONVERTERS = {
    PeerEntry: to_py_peer_entry,
    PulledEntry: to_py_pulled_entry,
    ResourceEntry: to_py_resource_entry,
    Resource: to_py_resource,
    ClientOptions: to_py_client_options,
}

FROM_PYTHON_CONVERTERS = {
    HyperdriveClientOptions: from_py_client_options,
    ResourceClientOptions: from_py_client_options,
    HyperdriveResource: from_py_resource
}
