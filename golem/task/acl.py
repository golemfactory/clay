import abc
import time

from pathlib import Path
from typing import Set, Union, Iterable

DENY_LIST_NAME = "deny.txt"
ALL_EXCEPT_ALLOWED = "ALL_EXCEPT_ALLOWED"
DEFAULT_TIMEOUT = 3600 * 24 * 30 * 12 * 10  # ~10 years (arbitrarily big)


class Acl(abc.ABC):
    @abc.abstractmethod
    def is_allowed(self, node_id: str) -> bool:
        pass

    @abc.abstractmethod
    def disallow(self, node_id: str, timeout_seconds: int, persist: bool) \
            -> None:
        pass


class _DenyAcl(Acl):
    def __init__(self, deny_coll: Iterable[str], list_path: Path) -> None:
        key_sequence = list(deny_coll)
        self._deny_deadlines = dict.fromkeys(key_sequence, self._deadline())
        self._list_path = list_path

    def is_allowed(self, node_id: str) -> bool:
        deadline = self._deny_deadlines.get(node_id)

        if deadline is None:
            return True

        elif deadline < time.time():
            self._deny_deadlines.pop(node_id, None)
            return True

        return False

    def disallow(self, node_id: str,
                 timeout_seconds: int = DEFAULT_TIMEOUT,
                 persist: bool = False) -> None:
        self._deny_deadlines[node_id] = self._deadline(timeout_seconds)

        if persist:
            deny_set = _read_set_from_file(self._list_path)
            if node_id not in deny_set:
                _write_set_to_file(self._list_path, deny_set | {node_id})

    @staticmethod
    def _deadline(timeout: int = DEFAULT_TIMEOUT):
        return time.time() + timeout


class _AllowAcl(Acl):
    def __init__(self, allow_set: Set[str], list_path: Path) -> None:
        self._allow_set = allow_set
        self._list_path = list_path

    def is_allowed(self, node_id: str) -> bool:
        return node_id in self._allow_set

    def disallow(self, node_id: str,
                 _timeout_seconds: int = 0,
                 persist: bool = False) -> None:
        self._allow_set.discard(node_id)

        if persist:
            allow_set = _read_set_from_file(self._list_path)
            if node_id in allow_set:
                _write_set_to_file(self._list_path, allow_set - {node_id})


def _read_set_from_file(path: Path) -> Set[str]:
    try:
        with path.open() as f:
            return set(line.strip() for line in f)
    except OSError:
        return set()


def _write_set_to_file(path: Path, node_set: Set[str]):
    with path.open('w') as f:
        for node_id in sorted(node_set):
            f.write(node_id + '\n')


def get_acl(datadir: Path) -> Union[_DenyAcl, _AllowAcl]:
    deny_list_path = datadir / DENY_LIST_NAME
    nodes_ids = _read_set_from_file(deny_list_path)

    if ALL_EXCEPT_ALLOWED in nodes_ids:
        nodes_ids.remove(ALL_EXCEPT_ALLOWED)
        return _AllowAcl(nodes_ids, deny_list_path)

    return _DenyAcl(nodes_ids, deny_list_path)
