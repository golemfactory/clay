import sys
from datetime import datetime
from pathlib import Path
from typing import NewType, Optional, Dict, Tuple, Iterable

from twisted.internet.defer import inlineCallbacks, FirstError

from golem.network.hyperdrive.client import HyperdriveAsyncClient
from golem.resource.client import ClientOptions

ResourceId = NewType('ResourceId', str)
Peers = Iterable[Dict[str, Tuple[str, int]]]


class ResourceManager:

    def __init__(
            self,
            client: HyperdriveAsyncClient,
    ) -> None:
        self._client = client
        self._cache: Dict[Path, ResourceId] = dict()
        self._cache_rev: Dict[ResourceId, Path] = dict()

    def build_client_options(
            self,
            **kwargs,
    ) -> ClientOptions:
        """ Return client-specific request options """

        return self._client.build_options(**kwargs)

    @inlineCallbacks
    def share(
            self,
            file_path: Path,
            client_options: ClientOptions,
    ):
        """ Share a single file; resolves to an assigned resource ID
            or a client-specific error """

        resolved_path = file_path.resolve()
        cached = self._cache.get(resolved_path)

        if cached:
            # Missing / invalid timeouts are validated by the client.
            # Don't pre-check it here and set the timeout to max int.
            timeout = client_options.timeout or sys.maxsize
            # Use system time like simple-transfer does
            now = datetime.now().timestamp()

            # Prevent crashes if the response is empty or invalid
            try:
                resource_info = yield self._client.resource_async(cached)
                valid_to = int(resource_info['validTo'])
            except (FirstError, KeyError, TypeError, ValueError):
                valid_to = 0

            if now + timeout <= valid_to:
                return cached
            self.drop(cached)

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
            client_options: ClientOptions,
    ):
        """ Download a single resource to a given directory;
            resolves to Path or a client-specific error """

        resolved_path = directory.resolve(strict=False)
        response = yield self._client.get_async(
            content_hash=resource_id,
            filepath=str(resolved_path),
            client_options=client_options)

        *_, files = response[0]
        return Path(files[0]).resolve()

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
