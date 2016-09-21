from gnr.customizers.paymentsdialogcustomizer import PaymentTableElem, IncomeTableElem
from golem.interface.command import command, Argument, CommandHelper, CommandResult

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


@command(argument=sort_incomes, help="Display incomes", root=True)
def incomes(sort):
    deferred = incomes.client.get_incomes_list()
    result = CommandHelper.wait_for(deferred) or []

    values = []

    for income in result:
        table_elem = IncomeTableElem(income)
        values.append([str(c.text()) for c in table_elem.cols])

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)


@command(argument=sort_payments, help="Display payments", root=True)
def payments(sort):

    deferred = payments.client.get_payments_list()
    result = CommandHelper.wait_for(deferred) or []

    values = []

    for payment in result:
        table_elem = PaymentTableElem(payment)
        values.append([str(c.text()) for c in table_elem.cols])

    return CommandResult.to_tabular(payments_table_headers, values, sort=sort)



