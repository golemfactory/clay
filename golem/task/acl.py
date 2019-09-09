import abc
import logging
import operator
import time
from enum import Enum
from typing import Dict, Union, Iterable, Optional, Tuple, List, cast
from sortedcontainers import SortedList
from golem.model import ACLAllowedNodes, ACLDeniedNodes, GenericKeyValue

from golem.core import common

logger = logging.getLogger(__name__)


class AclRule(Enum):
    allow = "allow"
    deny = "deny"


ACL_MODE_KEY = "ACL_MODE"
DEFAULT = AclRule.allow


class AclStatus:
    default_rule: AclRule
    rules: List[
        Tuple[
            Union[ACLAllowedNodes, ACLDeniedNodes],
            AclRule, Optional[int]
        ]
    ]

    def __init__(self,
                 default_rule: AclRule,
                 rules: List[
                     Tuple[
                         Union[ACLAllowedNodes, ACLDeniedNodes],
                         AclRule, Optional[int]
                     ]
                 ]) \
            -> None:
        self.default_rule = default_rule
        self.rules = rules

    def to_message(self) -> Dict:
        return {
            'default_rule': self.default_rule.value,
            'rules': [
                {
                    'node_id': identity.node_id,
                    'node_name': identity.node_name,
                    'rule': rule.value,
                    'deadline': deadline
                }
                for (identity, rule, deadline) in self.rules
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
        raise NotImplementedError

    @abc.abstractmethod
    def status(self) -> AclStatus:
        raise NotImplementedError


class _DenyAcl(Acl):
    class _Always:
        pass
    _always = _Always()

    _max_times: int
    # SortedList of floats = deadlines
    _deny_deadlines: Dict[str, Union[_Always, SortedList]]

    @classmethod
    def new_from_rules(cls, client, deny_coll: List[str]) -> '_DenyAcl':
        if len(deny_coll) > 0:
            peers = client.p2pservice.incoming_peers or dict()
            deny_list = []

            for key in deny_coll:
                node = peers[key]
                if node:
                    deny_list.append(ACLDeniedNodes(
                        {'node_id': key, 'node_name': node.name}))
            if len(deny_list) > 0:
                ACLDeniedNodes.insert_many(deny_list).execute()

        return cls(client)

    def __init__(self, client, max_times: int = 1) -> None:
        """
        :param max_times: how many times node_id must be disallowed to be
                          actually disallowed
        """
        self._deny_list = []
        self._client = client
        self._max_times = max_times
        self.read_list()

        self._deny_deadlines = dict((item.node_id, self._always)
                                    for item in self._deny_list)

    def read_list(self) -> None:
        nodes = ACLDeniedNodes.select().execute()
        self._deny_list = list(nodes)

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

        if persist and timeout_seconds == -1:
            try:
                existNode = ACLDeniedNodes.get(node_id=node_id)
            except ACLDeniedNodes.DoesNotExist:
                existNode = None
            if not existNode:
                peers = self._client.p2pservice.incoming_peers or dict()
                node = peers[node_id]
                node_db = ACLDeniedNodes(
                    node_id=node_id, node_name=node['node_name'])
                node_db.save()

    def allow(self, node_id: str, persist: bool = False) -> None:
        logger.info(
            'Whitelist node. node_id=%s, persist=%s',
            common.short_node_id(node_id),
            persist,
        )
        del self._deny_deadlines[node_id]

        if persist:
            try:
                existNode = ACLDeniedNodes.get(node_id=node_id)
            except ACLDeniedNodes.DoesNotExist:
                existNode = None

            if existNode:
                ACLDeniedNodes \
                    .delete() \
                    .where(ACLDeniedNodes.node_id == node_id) \
                    .execute()

    def status(self) -> AclStatus:
        _always = self._always
        now = time.time()

        self.read_list()

        def decode_deadline(deadline):
            if deadline is _always:
                return None
            return deadline[0]

        def get_node_by_id(node_id):
            return next((node for node in self._deny_list
                         if node.node_id == node_id), None)

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
            (get_node_by_id(identity),
             AclRule.deny,
             decode_deadline(deadline), )
            for (identity, deadline) in self._deny_deadlines.items()]
        return AclStatus(AclRule.allow, rules)

    @staticmethod
    def _deadline(timeout: int) -> float:
        return time.time() + timeout


class _AllowAcl(Acl):

    @classmethod
    def new_from_rules(cls, client, allow_coll: List[str]) -> '_AllowAcl':
        if len(allow_coll) > 0:
            peers = client.p2pservice.incoming_peers or dict()
            allow_list = []

            for key in allow_coll:
                node = peers[key]

                if node:
                    allow_list.append(ACLAllowedNodes(
                        {'node_id': key, 'node_name': node.name}))

            if len(allow_list) > 0:
                ACLAllowedNodes.insert_many(allow_list).execute()

        return cls(client)

    def __init__(self, client) -> None:

        self._allow_list = []
        self._client = client
        self.read_list()

    def read_list(self) -> None:
        nodes = ACLAllowedNodes.select().execute()
        self._allow_list = list(nodes)

    def is_allowed(self, node_id: str) -> Tuple[bool, Optional[DenyReason]]:
        if any(node for node in self._allow_list if node == node_id):
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
        self._allow_list = [x for x in self._allow_list if not (
            node_id == x.get('node_id'))]

        if persist:
            try:
                existNode = ACLAllowedNodes.get(node_id=node_id)
            except ACLAllowedNodes.DoesNotExist:
                existNode = None

            if existNode:
                ACLAllowedNodes \
                    .delete() \
                    .where(ACLAllowedNodes.node_id == node_id) \
                    .execute()

    def allow(self, node_id: str, persist: bool = False) -> None:
        logger.info(
            'Whitelist node. node_id=%s, persist=%s',
            common.short_node_id(node_id),
            persist,
        )
        peers = self._client.p2pservice.incoming_peers or dict()
        node = peers[node_id]
        node_model = ACLAllowedNodes(
            node_id=node_id, node_name=node['node_name'])
        self._allow_list.append(node_model)

        if persist:
            try:
                existNode = ACLAllowedNodes.get(node_id=node_id)
            except ACLAllowedNodes.DoesNotExist:
                existNode = None

            if not existNode:
                node_model.save()

    def status(self) -> AclStatus:
        self.read_list()
        rules = [
            (identity,
             AclRule.allow,
             cast(Optional[int], None))
            for identity in self._allow_list]

        return AclStatus(AclRule.deny, rules)


def get_acl(client, max_times: int = 1) -> Union[_DenyAcl, _AllowAcl]:

    try:
        value = GenericKeyValue.get(key=ACL_MODE_KEY)
    except GenericKeyValue.DoesNotExist:
        value = DEFAULT

    if value == AclRule.allow:
        return _AllowAcl(client)
    return _DenyAcl(client, max_times)


def setup_acl(client, default_rule: AclRule,
              exceptions: List[str]) -> Union[_DenyAcl, _AllowAcl]:

    if not default_rule in AclRule.__members__.values():
        raise ValueError('invalid acl default %r' % default_rule)

    entry, _ = GenericKeyValue.get_or_create(key=ACL_MODE_KEY)
    entry.value = default_rule.value
    entry.save()

    if default_rule == AclRule.deny:
        return _AllowAcl.new_from_rules(client, exceptions)
    return _DenyAcl.new_from_rules(client, exceptions)
