"""Ethereum related module with procedures exposed by RPC"""

import datetime
import functools
import typing

from golem_messages.datastructures import p2p as dt_p2p

from golem.core import common
from golem.network import nodeskeeper
from golem.rpc import utils as rpc_utils

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.ethereum.transactionsystem import TransactionSystem

def lru_node_factory():
    # Our version of peewee (2.10.2) doesn't support
    # .join(attr='XXX'). So we'll have to join manually
    lru_node = functools.lru_cache()(nodeskeeper.get)
    def _inner(node_id):
        if node_id is None:
            return None
        node = lru_node(node_id)
        if node is None:
            node = dt_p2p.Node(key=node_id)
        return node.to_dict()
    return _inner

class ETSProvider:
    """Provides ethereum related remote procedures that require ETS"""

    def __init__(self, ets: 'TransactionSystem'):
        self.ets = ets

    @rpc_utils.expose('pay.payments')
    def get_payments_list(
            self,
            num: typing.Optional[int] = None,
            last_seconds: typing.Optional[int] = None,
    ) -> typing.List[typing.Dict[str, typing.Any]]:
        interval = None
        if last_seconds is not None:
            interval = datetime.timedelta(seconds=last_seconds)
        lru_node = lru_node_factory()
        payments = self.ets.get_payments_list(num, interval)
        for payment in payments:
            payment['node'] = lru_node(payment['node'])
        return payments

    @rpc_utils.expose('pay.incomes')
    def get_incomes_list(self) -> typing.List[typing.Dict[str, typing.Any]]:
        incomes = self.ets.get_incomes_list()

        lru_node = lru_node_factory()

        def item(o):
            return {
                "subtask": common.to_unicode(o.subtask),
                "payer": common.to_unicode(o.sender_node),
                "value": common.to_unicode(o.value),
                "status": common.to_unicode(o.status.name),
                "transaction": common.to_unicode(o.transaction),
                "created": common.datetime_to_timestamp_utc(o.created_date),
                "modified": common.datetime_to_timestamp_utc(o.modified_date),
                "node": lru_node(o.sender_node),
            }

        return [item(income) for income in incomes]
