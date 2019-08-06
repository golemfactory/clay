import abc
import logging
import operator
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Set, Union, Iterable, Optional, Tuple, List, cast
from sortedcontainers import SortedList

from golem.core import common

logger = logging.getLogger(__name__)

DENY_LIST_NAME = "deny.txt"
ALL_EXCEPT_ALLOWED = "ALL_EXCEPT_ALLOWED"


class AclRule(Enum):
    allow = "allow"
    deny = "deny"


class AclStatus:
    default_rule: AclRule
    rules: List[Tuple[str, AclRule, Optional[int]]]

    def __init__(self,
                 default_rule: AclRule,
                 rules: List[Tuple[str, AclRule, Optional[int]]]) \
            -> None:
        self.default_rule = default_rule
        self.rules = rules

    def to_message(self):
        return {
            'default_rule': self.default_rule.value,
            'rules': [
                (ident, rule.value, deadline)
                for (ident, rule, deadline) in self.rules
            ]
        }


class DenyReason(Enum):
    blacklisted = "blacklisted"
    not_whitelisted = "not whitelisted"
    temporarily_blocked = "temporarily blocked"


class Acl(abc.ABC):
    @abc.abstractmethod
    def is_allowed(self, node_id: str) -> Tuple[bool, Optional[DenyReason]]:
        raise NotImplementedError

    @abc.abstractmethod
    def disallow(self, node_id: str, timeout_seconds: int, persist: bool) \
            -> None:
        raise NotImplementedError

    @abc.abstractmethod
    def allow(self, node_id: str, persist: bool) -> None:
        pass

    @abc.abstractmethod
    def status(self) -> AclStatus:
        pass


class _DenyAcl(Acl):
    class _Always:
        pass
    _always = _Always()

    _max_times: int
    # SortedList of floats = deadlines
    _deny_deadlines: Dict[str, Union[_Always, SortedList]]
    _list_path: Optional[Path]

    @classmethod
    def new_from_rules(cls, deny_coll: List[str],
                       list_path: Optional[Path]) -> '_DenyAcl':
        deny_set = set(deny_coll)
        if list_path is not None:
            _write_set_to_file(list_path, deny_set)
        return cls(deny_coll, list_path)

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
        while deadlines and deadlines[-1] <= now:
            del deadlines[-1]
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

    def allow(self, node_id: str, persist: bool) -> None:
        logger.info(
            'Whitelist node. node_id=%s, persist=%s',
            common.short_node_id(node_id),
            persist,
        )
        del self._deny_deadlines[node_id]
        if persist and self._list_path:
            deny_set = _read_set_from_file(self._list_path)
            if node_id in deny_set:
                _write_set_to_file(self._list_path, deny_set - {node_id})

    def status(self) -> AclStatus:
        _always = self._always
        now = time.time()

        def decode_deadline(deadline):
            if deadline is _always:
                return None
            return deadline[0]

        rules_to_remove = []
        for (identity, deadlines) in self._deny_deadlines.items():
            if isinstance(deadlines, SortedList):
                while deadlines and deadlines[0] < now:
                    del deadlines[0]
                if not deadlines:
                    rules_to_remove.append(identity)

        for identity in rules_to_remove:
            del self._deny_deadlines[identity]

        rules = [
            (identity,
             AclRule.deny,
             decode_deadline(deadline), )
            for (identity, deadline) in self._deny_deadlines.items()]
        return AclStatus(AclRule.allow, rules)

    @staticmethod
    def _deadline(timeout: int) -> float:
        return time.time() + timeout


class _AllowAcl(Acl):

    @classmethod
    def new_from_rules(cls, allow_coll: List[str],
                       list_path: Optional[Path]) -> '_AllowAcl':
        allow_set = set(allow_coll) | {ALL_EXCEPT_ALLOWED}
        if list_path is not None:
            _write_set_to_file(list_path, allow_set)
        return cls(set(allow_coll), list_path)

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

    def allow(self, node_id: str, persist: bool) -> None:
        logger.info(
            'Whitelist node. node_id=%s, persist=%s',
            common.short_node_id(node_id),
            persist,
        )
        self._allow_set.add(node_id)
        if persist and self._list_path:
            allow_set = _read_set_from_file(self._list_path)
            if node_id not in allow_set:
                _write_set_to_file(self._list_path, allow_set | {node_id})

    def status(self) -> AclStatus:
        rules = [
            (identity,
             AclRule.allow,
             cast(Optional[int], None))
            for identity in self._allow_set]

        return AclStatus(AclRule.deny, rules)


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


def setup_acl(datadir: Optional[Path],
              default_rule: AclRule,
              exceptions: List[str]) -> Union[_DenyAcl, _AllowAcl]:
    deny_list_path = datadir / DENY_LIST_NAME if datadir is not None else None
    if default_rule == AclRule.deny:
        return _AllowAcl.new_from_rules(exceptions, deny_list_path)
    if default_rule == AclRule.allow:
        return _DenyAcl.new_from_rules(exceptions, deny_list_path)
    raise ValueError('invalid acl default %r' % default_rule)
