from typing import List, Iterable, Tuple, Optional

from eth_utils import decode_hex

from golem.core.service import LoopingCallService
from golem.model import Payment

from .paymentskeeper import PaymentsKeeper
from .incomeskeeper import IncomesKeeper


class TransactionSystem(LoopingCallService):
    """ Transaction system.
    Keeps information about budget, expected payments, etc. """

    def __init__(self, payments_keeper=PaymentsKeeper(),
                 incomes_keeper=IncomesKeeper()):
        """ Create new transaction system instance.
        :param payments_keeper:
        default PaymentsKeeper, payment keeper class,
        an instance of this class
        while be used as a payment keeper
        """

        # Keeps information about payments to send
        self.payments_keeper = payments_keeper

        # Keeps information about received payments
        self.incomes_keeper = incomes_keeper

        super().__init__(13)

    def add_payment_info(  # pylint:disable=no-self-use
            self,
            subtask_id: str,
            value: int,
            eth_address: str):
        """ Add to payment keeper information about new payment for subtask.
        """
        payee = decode_hex(eth_address)
        if len(payee) != 20:
            raise ValueError(
                "Incorrect 'payee' length: {}. Should be 20".format(len(payee)))
        return Payment.create(
            subtask=subtask_id,
            payee=payee,
            value=value,
        )

    def get_payments_list(self):
        """ Return list of all planned and made payments
        :return list: list of dictionaries describing payments
        """
        return self.payments_keeper.get_list_of_all_payments()

    def get_total_payment_for_subtasks(self, subtask_ids: Iterable[str]) \
            -> Tuple[Optional[int], Optional[int]]:
        """
        Get total value and total fee for payments for the given subtask IDs
        **if all payments for the given subtasks are sent**
        :param subtask_ids: subtask IDs
        :return: (total_value, total_fee) if all payments are sent,
                (None, None) otherwise
        """
        return self.payments_keeper.get_total_payment_for_subtasks(subtask_ids)

    def get_incomes_list(self):
        """ Return list of all expected and received incomes
        :return list: list of dictionaries describing incomes
        """
        return self.incomes_keeper.get_list_of_all_incomes()

    def get_nodes_with_overdue_payments(self) -> List[str]:
        overdue_incomes = self.incomes_keeper.update_overdue_incomes()
        return [x.sender_node for x in overdue_incomes]

    def sync(self) -> None:
        pass
