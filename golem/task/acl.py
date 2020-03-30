import abc
import logging
import operator
import time
import ipaddress
from enum import Enum
from typing import Dict, Union, Optional, Tuple, List, cast
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
                    'identity': identity['node_id'],
                    'node_name': identity['node_name'] or "",
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
    def disallow(self, node_id: str, timeout_seconds: int) \
            -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def allow(self, node_id: str, persist: bool) -> bool:
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
        if deny_coll:
            deny_list = []

            for key in deny_coll:
                node = _get_node_info(client, key)

                if node:
                    deny_list.append(
                        {'node_id': key, 'node_name': node['node_name']})
            if deny_list:
                ACLDeniedNodes.insert_many(deny_list).execute()

        return cls(client)

    def __init__(self, client, max_times: int = 1) -> None:
        """
        :param max_times: how many times node_id must be disallowed to be
                          actually disallowed
        """
        self._deny_list = []  # type: List[ACLDeniedNodes]
        self._client = client
        self._max_times = max_times
        self._read_list()

        self._deny_deadlines = dict((item.node_id, self._always)
                                    for item in self._deny_list)

    def _read_list(self) -> None:
        nodes = ACLDeniedNodes.select().execute()
        self._deny_list = list(set(self._deny_list + list(nodes)))

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
                 timeout_seconds: int = -1) -> bool:
        persist = timeout_seconds < 0
        logger.info(
            'Banned node. node_id=%s, timeout=%ds, persist=%s',
            common.short_node_id(node_id),
            timeout_seconds,
            persist
        )
        if persist:
            self._deny_deadlines[node_id] = self._always
        else:
            if node_id not in self._deny_deadlines:
                self._deny_deadlines[node_id] = SortedList(key=operator.neg)
            node_deadlines = self._deny_deadlines[node_id]

            if node_deadlines is self._always:
                return False

            assert isinstance(node_deadlines, SortedList)
            node_deadlines.add(self._deadline(timeout_seconds))

        if persist:
            try:
                ACLDeniedNodes.get(node_id=node_id)
                return False
            except ACLDeniedNodes.DoesNotExist:
                peers = self._client.p2pservice.incoming_peers or dict()
                if node_id in peers:
                    node = peers[node_id]
                else:
                    node = dict(node_name="Unknown")
                node_db = ACLDeniedNodes(
                    node_id=node_id, node_name=node['node_name'])
                node_db.save()
        return True

    def allow(self, node_id: str, persist: bool = False) -> bool:
        logger.info(
            'Whitelist node. node_id=%s, persist=%s',
            common.short_node_id(node_id),
            persist,
        )
        if node_id in self._deny_deadlines:
            del self._deny_deadlines[node_id]

        if persist:
            try:
                ACLDeniedNodes.get(node_id=node_id)
            except ACLDeniedNodes.DoesNotExist:
                return False
            finally:
                ACLDeniedNodes \
                    .delete() \
                    .where(ACLDeniedNodes.node_id == node_id) \
                    .execute()
        return True

    def status(self) -> AclStatus:
        _always = self._always
        now = time.time()

        self._read_list()

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
            ({
                'node_id': identity,
                'node_name': _get_node_info(
                    self._client, identity)['node_name']
            },
             AclRule.deny,
             decode_deadline(deadline))
            for (identity, deadline) in self._deny_deadlines.items()]
        return AclStatus(AclRule.allow, rules)

    @staticmethod
    def _deadline(timeout: int) -> float:
        return time.time() + timeout


class _AllowAcl(Acl):

    @classmethod
    def new_from_rules(cls, client, allow_coll: List[str]) -> '_AllowAcl':
        if allow_coll:
            allow_list = []
            for key in allow_coll:
                node = _get_node_info(client, key)
                if node:
                    allow_list.append(
                        {'node_id': key, 'node_name': node['node_name']})
            if allow_list:
                ACLAllowedNodes.insert_many(allow_list).execute()

        return cls(client)

    def __init__(self, client) -> None:

        self._allow_list = []  # type: List[ACLAllowedNodes]
        self._client = client
        self._read_list()

    def _read_list(self) -> None:
        nodes = ACLAllowedNodes.select().execute()
        self._allow_list = list(set(self._allow_list + list(nodes)))

    def is_allowed(self, node_id: str) -> Tuple[bool, Optional[DenyReason]]:
        if any(node for node in self._allow_list if node.node_id == node_id):
            return True, None

        return False, DenyReason.not_whitelisted

    def disallow(self, node_id: str,
                 timeout_seconds: int = -1) -> bool:
        persist = timeout_seconds < 0
        if persist:
            logger.info(
                'Removed node. node_id=%s, timeout=%ds, persist=True',
                common.short_node_id(node_id),
                timeout_seconds
            )
            self._allow_list = [node for node in self._allow_list if not (
                node_id == node.node_id)]
            try:
                ACLAllowedNodes.get(node_id=node_id)
            except ACLAllowedNodes.DoesNotExist:
                return False
            finally:
                ACLAllowedNodes \
                    .delete() \
                    .where(ACLAllowedNodes.node_id == node_id) \
                    .execute()
        return True

    def allow(self, node_id: str, persist: bool = False) -> bool:
        logger.info(
            'Whitelist node. node_id=%s, persist=%s',
            common.short_node_id(node_id),
            persist,
        )
        node = _get_node_info(self._client, node_id)
        node_model = ACLAllowedNodes(
            node_id=node_id, node_name=node['node_name'])

        if not any(node for node in self._allow_list if (
                node.node_id == node_id)):
            self._allow_list.append(node_model)

        if persist:
            try:
                ACLAllowedNodes.get(node_id=node_id)
                return False
            except ACLAllowedNodes.DoesNotExist:
                node_model.save()
        return True

    def status(self) -> AclStatus:
        self._read_list()
        rules = [
            (identity.to_dict(),
             AclRule.allow,
             cast(Optional[int], None))
            for identity in self._allow_list]

        return AclStatus(AclRule.deny, rules)


def get_acl(client, max_times: int = 1) -> Union[_DenyAcl, _AllowAcl]:
    try:
        acl_key = GenericKeyValue.get(key=ACL_MODE_KEY).value
    except GenericKeyValue.DoesNotExist:
        acl_key = DEFAULT
    if acl_key == AclRule.deny.value:
        return _AllowAcl(client)
    return _DenyAcl(client, max_times)


def setup_acl(client, default_rule: AclRule,
              exceptions: List[str]) -> Union[_DenyAcl, _AllowAcl]:

    if default_rule not in AclRule.__members__.values():
        raise ValueError('invalid acl default %r' % default_rule)

    entry, _ = GenericKeyValue.get_or_create(key=ACL_MODE_KEY)
    entry.value = default_rule.value
    entry.save()

    if default_rule == AclRule.deny:
        return _AllowAcl.new_from_rules(client, exceptions)
    return _DenyAcl.new_from_rules(client, exceptions)


def _get_node_info(client, key: str) -> Dict:
    peers = client.p2pservice.incoming_peers or dict()
    try:
        ipaddress.ip_address(key)
        node = next((peers[node] for node in peers
                     if peers[node]['address'] == key),
                    {'node_id': key, 'node_name': None})
    except ValueError:
        node = peers[key] if key in peers else {
            'node_id': key, 'node_name': None}

    return node
