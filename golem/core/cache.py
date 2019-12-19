import time
import typing

from dataclasses import dataclass


@dataclass()
class CacheEntry:
    value: object
    timestamp: float


class MemCacheMixin:
    @property
    def _cache(self) -> typing.Dict[str, CacheEntry]:
        if not hasattr(self, '_cache_store'):
            self._cache_store: typing.Dict[str, CacheEntry] = {}
        return self._cache_store

    def cache_get(self, key, **kwargs) -> object:
        """Returns value

        Unless `default` keyword argument is specified,
        will raise KeyError if key is not found in cache.
        """
        try:
            return self._cache[key].value
        except KeyError:
            if 'default' in kwargs:
                return kwargs['default']
            raise

    def cache_set(self, key, value) -> None:
        entry = CacheEntry(value=value, timestamp=time.time())
        self._cache[key] = entry

    def cache_lastmod(self, key) -> typing.Optional[float]:
        try:
            return self._cache[key].timestamp
        except KeyError:
            return None
