from ethereum.utils import denoms

from golem.core.common import to_unicode
from golem.core.deferred import sync_wait
from golem.interface.command import command, Argument, CommandResult

incomes_table_headers = ['payer', 'status', 'value']
payments_table_headers = ['subtask', 'payee', 'status', 'value', 'fee']

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


def __value(value):
    return "{:.6f} GNT".format(float(value) / denoms.ether)


@command(argument=sort_incomes, help="Display incomes", root=True)
def incomes(sort):
    deferred = incomes.client.get_incomes_list()
    result = sync_wait(deferred) or []

    values = []

    for income in result:
        entry = [
            to_unicode(income["payer"]),
            to_unicode(income["status"]),
            __value(float(income["value"])),
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
            payment_fee = "{:.1f}%".format(float(payment_fee) * 100 /
                                            payment_value)

        entry = [
            to_unicode(payment["subtask"]),
            to_unicode(payment["payee"]),
            to_unicode(payment["status"]),
            __value(payment_value),
            to_unicode(payment_fee)
        ]

        values.append(entry)

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)
