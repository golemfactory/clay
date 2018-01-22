import abc
from pathlib import Path
from typing import Set


DENY_LIST_NAME = "deny.txt"
ALLOW_LIST_NAME = "allow.txt"
ALL_EXCEPT_ALLOWED = "ALL_EXCEPT_ALLOWED"


class Acl(abc.ABC):
    @abc.abstractmethod
    def is_allowed(self, node_id: str) -> bool:
        pass

    @abc.abstractmethod
    def disallow(self, node_id: str) -> None:
        pass


class _DenyAcl(Acl):
    def __init__(self, deny_set: Set[str]):
        self._deny_set = deny_set

    def is_allowed(self, node_id: str) -> bool:
        return node_id not in self._deny_set

    def disallow(self, node_id: str) -> None:
        self._deny_set.add(node_id)


class _AllowAcl(Acl):
    def __init__(self, allow_set: Set[str]):
        self._allow_set = allow_set

    def is_allowed(self, node_id: str) -> bool:
        return node_id in self._allow_set

    def disallow(self, node_id: str) -> None:
        self._allow_set.discard(node_id)


def _read_set_from_file(path: Path) -> Set[str]:
    try:
        with path.open() as f:
            return set(line.strip() for line in f)
    except OSError:
        return set()


def get_acl(datadir: Path) -> Acl:
    deny_set = _read_set_from_file(datadir / DENY_LIST_NAME)

    if ALL_EXCEPT_ALLOWED in deny_set:
        allow_set = _read_set_from_file(datadir / ALLOW_LIST_NAME)
        return _AllowAcl(allow_set)

    return _DenyAcl(deny_set)
