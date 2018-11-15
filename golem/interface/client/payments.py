from ethereum.utils import denoms

from golem.core.common import to_unicode
from golem.core.deferred import sync_wait
from golem.interface.command import command, Argument, CommandResult

incomes_table_headers = ['payer', 'status', 'value']
payments_table_headers = ['subtask', 'payee', 'status', 'value', 'fee']
deposit_payments_table_headers = ['tx', 'status', 'value', 'fee']

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


def __value(value, currency):
    return f"{float(value) / denoms.ether:.8f} {currency}"


@command(argument=sort_incomes, help="Display incomes", root=True)
def incomes(sort):
    deferred = incomes.client.get_incomes_list()
    result = sync_wait(deferred) or []

    values = []

    for income in result:
        entry = [
            to_unicode(income["payer"]),
            to_unicode(income["status"]),
            __value(float(income["value"]), "GNT"),
        ]
        values.append(entry)

    return CommandResult.to_tabular(incomes_table_headers, values, sort=sort)


@command(argument=sort_payments, help="Display payments", root=True)
def payments(sort):

    deferred = payments.client.get_payments_list()
    result = sync_wait(deferred) or []

    values = []

    for payment in result:

        payment_value = float(payment["value"])
        payment_fee = payment["fee"] or ""

        if payment_fee:
            payment_fee = __value(payment_fee, "ETH")

        entry = [
            to_unicode(payment["subtask"]),
            to_unicode(payment["payee"]),
            to_unicode(payment["status"]),
            __value(payment_value, "GNT"),
            to_unicode(payment_fee)
        ]

        values.append(entry)

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)


@command(
    argument=sort_deposit_payments,
    help="Display deposit payments",
    root=True,
)
def deposit_payments(sort):

    deferred = payments.client.get_deposit_payments_list()
    result = sync_wait(deferred) or []

    values = []

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
