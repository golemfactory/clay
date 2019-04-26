import abc
import logging
import operator
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Set, Union, Iterable, Optional, Tuple
from sortedcontainers import SortedList

from golem.core import common

logger = logging.getLogger(__name__)

DENY_LIST_NAME = "deny.txt"
ALL_EXCEPT_ALLOWED = "ALL_EXCEPT_ALLOWED"


class DenyReason(Enum):
    blacklisted = "blacklisted"
    not_whitelisted = "not whitelisted"
    temporarily_blocked = "temporarily blocked"


class Acl(abc.ABC):
    @abc.abstractmethod
    def is_allowed(self, node_id: str) -> Tuple[bool, Optional[DenyReason]]:
        pass

    @abc.abstractmethod
    def disallow(self, node_id: str, timeout_seconds: int, persist: bool) \
            -> None:
        pass


class _DenyAcl(Acl):
    class _Always:
        pass
    _always = _Always()

    _max_times: int
    # SortedList of floats = deadlines
    _deny_deadlines: Dict[str, Union[_Always, SortedList]]
    _list_path: Optional[Path]

    def __init__(self, deny_coll: Optional[Iterable[str]] = None,
                 list_path: Optional[Path] = None, max_times: int = 1) -> None:
        """
        :param max_times: how many times node_id must be disallowed to be
                          actually disallowed
        """
        if deny_coll is None:
            deny_coll = []
        self._max_times = max_times
        self._deny_deadlines = dict((key, self._always) for key in deny_coll)
        self._list_path = list_path

    def is_allowed(self, node_id: str) -> Tuple[bool, Optional[DenyReason]]:
        if node_id not in self._deny_deadlines:
            return True, None

        deadlines = self._deny_deadlines[node_id]

        if deadlines is self._always:
            return False, DenyReason.blacklisted

        assert isinstance(deadlines, SortedList)
        now = time.time()
        while deadlines and deadlines[0] <= now:
            del deadlines[0]
        if not deadlines:
            del self._deny_deadlines[node_id]

        if len(deadlines) >= self._max_times:
            return False, DenyReason.temporarily_blocked

        return True, None

    def disallow(self, node_id: str,
                 timeout_seconds: int = -1,
                 persist: bool = False) -> None:
        logger.info(
            'Banned node. node_id=%s, timeout=%ds, persist=%s',
            common.short_node_id(node_id),
            timeout_seconds,
            persist,
        )
        if timeout_seconds < 0:
            self._deny_deadlines[node_id] = self._always
        else:
            if node_id not in self._deny_deadlines:
                self._deny_deadlines[node_id] = SortedList(key=operator.neg)
            node_deadlines = self._deny_deadlines[node_id]
            if node_deadlines is self._always:
                return
            assert isinstance(node_deadlines, SortedList)
            node_deadlines.add(self._deadline(timeout_seconds))

        if persist and timeout_seconds == -1 and self._list_path:
            deny_set = _read_set_from_file(self._list_path)
            if node_id not in deny_set:
                _write_set_to_file(self._list_path, deny_set | {node_id})

    @staticmethod
    def _deadline(timeout: int) -> float:
        return time.time() + timeout


class _AllowAcl(Acl):
    def __init__(
            self,
            allow_set: Optional[Set[str]] = None,
            list_path: Optional[Path] = None,
    ) -> None:
        if allow_set is None:
            allow_set = set()
        self._allow_set = allow_set
        self._list_path = list_path

    def is_allowed(self, node_id: str) -> Tuple[bool, Optional[DenyReason]]:
        if node_id in self._allow_set:
            return True, None

        return False, DenyReason.not_whitelisted

    def disallow(self, node_id: str,
                 timeout_seconds: int = 0,
                 persist: bool = False) -> None:
        logger.info(
            'Banned node. node_id=%s, timeout=%ds, persist=%s',
            common.short_node_id(node_id),
            timeout_seconds,
            persist,
        )
        self._allow_set.discard(node_id)

        if persist and self._list_path:
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


def get_acl(datadir: Path, max_times: int = 1) -> Union[_DenyAcl, _AllowAcl]:
    deny_list_path = datadir / DENY_LIST_NAME
    nodes_ids = _read_set_from_file(deny_list_path)

    if ALL_EXCEPT_ALLOWED in nodes_ids:
        nodes_ids.remove(ALL_EXCEPT_ALLOWED)
        return _AllowAcl(nodes_ids, deny_list_path)

    return _DenyAcl(nodes_ids, deny_list_path, max_times)
