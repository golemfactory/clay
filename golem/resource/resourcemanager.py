from typing import NewType, Optional, Dict, Tuple, Iterable

from pathlib import Path
from twisted.internet.defer import inlineCallbacks

from golem.network.hyperdrive.client import HyperdriveAsyncClient
from golem.resource.client import ClientOptions

ResourceId = NewType('ResourceId', str)
Peers = Iterable[Dict[str, Tuple[str, int]]]


class ResourceManager:

    Client = HyperdriveAsyncClient

    def __init__(
            self,
            port: int,
            host: str,
    ) -> None:
        self._client = self.Client(port, host)
        self._cache: Dict[Path, ResourceId] = dict()
        self._cache_rev: Dict[ResourceId, Path] = dict()

    @classmethod
    def build_client_options(
            cls,
            peers: Optional[Peers] = None,
            **kwargs,
    ) -> ClientOptions:
        """ Return client-specific request options """

        return cls.Client.build_options(
            peers=peers, **kwargs)

    @inlineCallbacks
    def share(
            self,
            file_path: Path,
            client_options: Optional[ClientOptions] = None,
    ):
        """ Share a single file; resolves to an assigned resource ID
            or a client-specific error """

        resolved_path = file_path.resolve()
        cached = self._cache.get(resolved_path)
        if cached:
            return cached

        resource_id = yield self._client.add_async(
            files={str(resolved_path): resolved_path.name},
            client_options=client_options)

        self._cache[resolved_path] = resource_id
        self._cache_rev[resource_id] = resolved_path

        return resource_id

    @inlineCallbacks
    def download(
            self,
            resource_id: ResourceId,
            directory: Path,
            client_options: Optional[ClientOptions] = None,
    ):
        """ Download a single resource to a given directory;
            resolves to Path or a client-specific error """

        resolved_path = directory.resolve(strict=False)
        _, files = yield self._client.get_async(
            content_hash=resource_id,
            filepath=str(resolved_path),
            client_options=client_options)

        first_file = files[0]
        file_path = Path(first_file).resolve()
        return file_path

    @inlineCallbacks
    def drop(
            self,
            resource_id: ResourceId,
    ):
        """ Stop a single resource ID from being shared """

        yield self._client.cancel_async(resource_id)
        path = self._cache_rev.pop(resource_id, None)
        if path is not None:
            self._cache.pop(path, None)
