from ethereum.utils import denoms

from golem.core.deferred import sync_wait
from golem.interface.command import command, Argument, CommandResult

incomes_table_headers = ['payer', 'status', 'value', 'block']
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


def __status(info):
    return unicode(info["status"]).replace(u"PaymentStatus.", u"")


def __value(value):
    return u"{:.6f} GNT".format(value / denoms.ether)


@command(argument=sort_incomes, help="Display incomes", root=True)
def incomes(sort):
    deferred = incomes.client.get_incomes_list()
    result = sync_wait(deferred) or []

    values = []

    for income in result:
        entry = [
            income["payer"].encode('hex'),
            __status(income),
            __value(float(income["value"])),
            str(income["block_number"])
        ]
        values.append(entry)

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)


@command(argument=sort_payments, help="Display payments", root=True)
def payments(sort):

    deferred = payments.client.get_payments_list()
    result = sync_wait(deferred) or []

    values = []

    for payment in result:

        payment_value = float(payment["value"])
        payment_fee = payment["fee"] or u""

        if payment_fee:
            payment_fee = u"{:.1f}%".format(float(payment_fee) * 100 /
                                            payment_value)

        entry = [
            payment["subtask"],
            payment["payee"].encode('hex'),
            __status(payment),
            __value(payment_value),
            payment_fee
        ]

        values.append(entry)

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)



