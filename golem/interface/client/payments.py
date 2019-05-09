# pylint: disable=protected-access
from ethereum.utils import denoms

from golem.core.common import to_unicode, short_node_id
from golem.core.deferred import sync_wait
from golem.interface.command import command, Argument, CommandResult

incomes_table_headers = ['payer', 'status', 'value']
payments_table_headers = ['subtask', 'payee', 'status', 'value', 'fee']
deposit_payments_table_headers = ['tx', 'status', 'value', 'fee']

filterable_statuses = ['awaiting', 'confirmed']

full_table = Argument(
    '--full',
    optional=True,
    default=False,
    help="Expand shortened columns"
)

sort_incomes = Argument(
    '--sort',
    choices=incomes_table_headers,
    optional=True,
    default=None,
    help="Sort incomes"
)

sort_payments = Argument(
    '--sort',
    choices=payments_table_headers,
    optional=True,
    default=None,
    help="Sort payments"
)

sort_deposit_payments = Argument(
    '--sort',
    choices=deposit_payments_table_headers,
    optional=True,
    default=None,
    help="Sort deposit payments",
)

status_filter = Argument(
    'status',
    optional=True,
    choices=filterable_statuses,
    help="Filter by status"
)


def __value(value, currency):
    return f"{float(value) / denoms.ether:.8f} {currency}"


def filter_by_status(results, status):
    return [v for v in results if v['status'] == status]


@command(arguments=(sort_incomes, status_filter, full_table),
         help="Display incomes", root=True)
def incomes(sort, status, full=False):
    deferred = incomes.client._call('pay.incomes')
    result = sync_wait(deferred) or []

    values = []
    if status is not None:
        result = filter_by_status(result, status)

    for income in result:
        payer_str = to_unicode(income["payer"])
        entry = [
            payer_str if full else short_node_id(payer_str),
            to_unicode(income["status"]),
            __value(float(income["value"]), "GNT"),
        ]
        values.append(entry)

    return CommandResult.to_tabular(incomes_table_headers, values, sort=sort)


@command(arguments=(sort_payments, status_filter, full_table),
         help="Display payments", root=True)
def payments(sort, status, full=False):

    deferred = payments.client._call('pay.payments')
    result = sync_wait(deferred) or []

    values = []
    if status is not None:
        result = filter_by_status(result, status)

    for payment in result:

        payment_value = float(payment["value"])
        payment_fee = payment["fee"] or ""
        payee_str = to_unicode(payment["payee"])

        if payment_fee:
            payment_fee = __value(payment_fee, "ETH")

        entry = [
            to_unicode(payment["subtask"]),
            payee_str if full else short_node_id(payee_str),
            to_unicode(payment["status"]),
            __value(payment_value, "GNT"),
            to_unicode(payment_fee)
        ]

        values.append(entry)

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)


@command(
    arguments=(sort_deposit_payments, status_filter),
    help="Display deposit payments",
    root=True,
)
def deposit_payments(sort, status):

    deferred = payments.client._call('pay.deposit_payments')
    result = sync_wait(deferred) or []

    values = []
    if status is not None:
        result = filter_by_status(result, status)

    for payment in result:

        payment_value = float(payment["value"])
        payment_fee = payment["fee"] or ""

        if payment_fee:
            payment_fee = __value(payment_fee, "ETH")

        entry = [
            to_unicode(payment["tx"]),
            to_unicode(payment["status"]),
            __value(payment_value, "GNT"),
            to_unicode(payment_fee)
        ]

        values.append(entry)

    return CommandResult.to_tabular(
        deposit_payments_table_headers,
        values,
        sort=sort
    )
