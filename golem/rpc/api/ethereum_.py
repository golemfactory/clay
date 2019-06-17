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
    from golem import model
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

    @rpc_utils.expose('pay.gas_price')
    def get_gas_price(self) -> typing.Dict[str, str]:
        return {
            "current_gas_price": str(self.ets.gas_price),
            "gas_price_limit": str(self.ets.gas_price_limit)
        }

    @rpc_utils.expose('pay.ident')
    def get_payment_address(self) -> str:
        return self.ets.get_payment_address()

    @rpc_utils.expose('pay.deposit_payments')
    def get_deposit_payments_list(
            self,
            limit=1000,
            offset=0,
    ) -> typing.List[typing.Dict[str, typing.Any]]:
        operations: 'typing.List[model.WalletOperation]' = \
            self.ets.get_deposit_payments_list(
                limit=limit,
                offset=offset,
            )
        result = []
        for dpayment in operations:
            entry = {}
            entry['value'] = common.to_unicode(dpayment.amount)
            entry['status'] = common.to_unicode(
                dpayment.status.name,
            )
            entry['fee'] = common.to_unicode(
                dpayment.gas_cost,
            )
            entry['transaction'] = common.to_unicode(
                dpayment.tx_hash,
            )
            entry['created'] = common.datetime_to_timestamp_utc(
                dpayment.created_date,
            )
            entry['modified'] = common.datetime_to_timestamp_utc(
                dpayment.modified_date,
            )
            result.append(entry)
        return result

    @rpc_utils.expose('pay.deposit.relock')
    def concent_relock(self) -> None:
        self.ets.concent_relock()

    @rpc_utils.expose('pay.deposit.unlock')
    def concent_unlock(self) -> None:
        self.ets.concent_unlock()
