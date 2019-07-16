from functools import partial
from typing import NewType, Optional, Dict, Tuple, Iterable

from pathlib import Path
from twisted.internet.defer import Deferred, succeed

from golem.network.hyperdrive.client import HyperdriveAsyncClient
from golem.resource.client import ClientOptions

ResourceId = NewType('ResourceId', str)


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
            peers=None,
            **kwargs
    ) -> ClientOptions:
        """ Returns client-specific request options """

        return cls.Client.build_options(
            peers=peers, **kwargs)

    def share(
            self,
            file_path: Path,
            client_options: Optional[ClientOptions] = None,
    ) -> Deferred:
        """ Shares a single file; returns a future which resolves to
            an assigned resource ID or a client-specific error """

        resolved_path = file_path.resolve()
        cached = self._cache.get(resolved_path)
        if cached:
            return succeed(cached)

        deferred = self._client.add_async(
            files={str(resolved_path): resolved_path.name},
            client_options=client_options)
        deferred.addCallback(partial(self._shared, resolved_path))

        return deferred

    def download(
            self,
            resource_id: ResourceId,
            directory: Path,
            client_options: Optional[ClientOptions] = None,
    ) -> Deferred:
        """ Downloads a single resource to a given directory;
            returns a future which resolves to Tuple[ResourceId, Path]
            or a client-specific error """

        resolved_path = directory.resolve(strict=False)

        deferred = self._client.get_async(
            content_hash=resource_id,
            filepath=str(resolved_path),
            client_options=client_options)
        deferred.addCallback(self._downloaded)

        return deferred

    def drop(
            self,
            resource_id: ResourceId,
    ) -> Deferred:
        """ Stops a single resource ID from being shared;
            returns a future which resolves to a ResourceId or
            a client-specific error """

        deferred = self._client.cancel_async(resource_id)
        deferred.addCallback(self._dropped)
        return deferred

    def _shared(
            self,
            path: Path,
            resource_id: ResourceId,
    ) -> ResourceId:
        """ Caches a resource ID and passes it down the callback chain """

        self._cache[path] = resource_id
        self._cache_rev[resource_id] = path
        return resource_id

    @staticmethod
    def _downloaded(
            result: Tuple[ResourceId, Iterable[str]],
    ) -> Tuple[ResourceId, Path]:
        """ Translates a response and passes it down the callback chain """

        resource_id, files = result
        first_file = next(iter(files))
        file_path = Path(first_file).resolve()
        return resource_id, file_path

    def _dropped(
            self,
            resource_id: ResourceId,
    ) -> ResourceId:
        """ Removes a resource ID from cache """

        path = self._cache_rev.pop(resource_id, None)
        if path is not None:
            self._cache.pop(path, None)
        return resource_id
