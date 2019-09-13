"""Ethereum related module with procedures exposed by RPC"""

import datetime
import functools
import logging
import typing

from golem_messages.datastructures import p2p as dt_p2p

from golem import model
from golem.core import common
from golem.network import nodeskeeper
from golem.rpc import utils as rpc_utils

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.ethereum.transactionsystem import TransactionSystem
logger = logging.getLogger(__name__)


def lru_node_factory():
    # Our version of peewee (2.10.2) doesn't support
    # .join(attr='XXX'). So we'll have to join manually
    lru_node = functools.lru_cache()(nodeskeeper.get)

    def _inner(node_id):
        if node_id is None:
            return None
        if node_id.startswith('0x'):
            node_id = node_id[2:]
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
            node_id = o.node if not o.node.startswith('0x') else o.node[2:]
            return {
                "subtask": common.to_unicode(o.subtask),
                "payer": common.to_unicode(node_id),
                "value": common.to_unicode(o.wallet_operation.amount),
                "status": common.to_unicode(o.wallet_operation.status.name),
                "transaction": common.to_unicode(o.wallet_operation.tx_hash),
                "created": common.datetime_to_timestamp_utc(o.created_date),
                "modified": common.datetime_to_timestamp_utc(o.modified_date),
                "node": lru_node(o.node),
            }

        return [item(income) for income in incomes]

    @rpc_utils.expose('pay.operations')
    @staticmethod
    def get_operations(
            operation_type: typing.Optional[str],
            page_num: int = 1,
            per_page: int = 20,
    ):
        assert page_num > 0
        assert per_page > 0
        lru_node = lru_node_factory()
        # Unfortunately we can't use LEFT OUTER JOIN
        # because peewees implementation doesn't return
        # joined models.
        query = model.WalletOperation.select() \
            .order_by(model.WalletOperation.id.desc())
        if operation_type:
            try:
                operation_type = model.WalletOperation.TYPE(operation_type)
            except ValueError:
                logger.error('Invalid operation type: %r', operation_type)
                return []
            query = query.where(
                model.WalletOperation.operation_type == operation_type,
            )
        query = query.paginate(page_num, per_page)
        tp_query = model.TaskPayment.select() \
            .where(
                model.TaskPayment.wallet_operation.in_(query),
            )
        task_payments_map = {tp.id: tp for tp in tp_query}

        def payment(wallet_operation_id: int) -> typing.Optional[dict]:
            if wallet_operation_id not in task_payments_map:
                return None
            o = task_payments_map[wallet_operation_id]
            return {
                'node': lru_node(o.node),
                'task_id': o.task,
                'subtask_id': o.subtask,
                'charged_from_deposit': o.charged_from_deposit,
                'accepted_ts': str(o.accepted_ts) if o.accepted_ts else None,
                'settled_ts': str(o.settled_ts) if o.settled_ts else None,
                'missing_amount': str(o.missing_amount),
                'created': common.datetime_to_timestamp_utc(o.created_date),
                'modified': common.datetime_to_timestamp_utc(o.modified_date),
            }

        def operation(o: model.WalletOperation):
            return {
                'task_payment': payment(o.id),
                'transaction_hash': o.tx_hash,
                'direction': str(o.direction.value),
                'operation_type': str(o.operation_type.value),
                'status': str(o.status.value),
                'sender_address': str(o.sender_address),
                'recipient_address': str(o.recipient_address),
                'amount': str(o.amount),
                'currency': str(o.currency.value),
                'gas_cost': str(o.gas_cost),
                'created': common.datetime_to_timestamp_utc(o.created_date),
                'modified': common.datetime_to_timestamp_utc(o.modified_date),
            }
        return [operation(o) for o in query]

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
