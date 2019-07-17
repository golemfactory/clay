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
            **kwargs
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
        """ Share a single file; return a future which resolves to
            an assigned resource ID or a client-specific error """

        resolved_path = file_path.resolve()
        cached = self._cache.get(resolved_path)
        if cached:
            return cached

        resource_id = yield self._client.add_async(
            files={str(resolved_path): resolved_path.name},
            client_options=client_options)

        self._shared(resolved_path, resource_id)
        return resource_id

    @inlineCallbacks
    def download(
            self,
            resource_id: ResourceId,
            directory: Path,
            client_options: Optional[ClientOptions] = None,
    ):
        """ Download a single resource to a given directory;
            return a future which resolves to Tuple[ResourceId, Path]
            or a client-specific error """

        resolved_path = directory.resolve(strict=False)
        response = yield self._client.get_async(
            content_hash=resource_id,
            filepath=str(resolved_path),
            client_options=client_options)

        return self._parse_download_response(response)

    @inlineCallbacks
    def drop(
            self,
            resource_id: ResourceId,
    ):
        """ Stop a single resource ID from being shared;
            return a future which resolves to a ResourceId or
            a client-specific error """

        yield self._client.cancel_async(resource_id)
        self._dropped(resource_id)

    def _shared(
            self,
            path: Path,
            resource_id: ResourceId,
    ) -> None:
        """ Cache the resource ID """

        self._cache[path] = resource_id
        self._cache_rev[resource_id] = path

    def _dropped(
            self,
            resource_id: ResourceId,
    ) -> None:
        """ Remove the resource ID from cache """

        path = self._cache_rev.pop(resource_id, None)
        if path is not None:
            self._cache.pop(path, None)

    @staticmethod
    def _parse_download_response(
            result: Tuple[ResourceId, Iterable[str]],
    ) -> Tuple[ResourceId, Path]:
        """ Translate the download response w.r.t. only sharing single files """

        resource_id, files = result
        first_file = next(iter(files))
        file_path = Path(first_file).resolve()
        return resource_id, file_path
