import logging
from datetime import datetime

from golem.core.common import datetime_to_timestamp
from golem.model import Payment

logger = logging.getLogger(__name__)


class PaymentsDatabase(object):
    """ Save and retrieve from database information about payments that this node has to make / made
    """

    @staticmethod
    def get_payment_value(payment_info):
        """ Return value of a payment that was done to the same node and for the same task as payment for payment_info
        :param PaymentInfo payment_info: payment structure from which the
               database should retrieve information about computing node and
               task id.
        :return int: value of a previous similiar payment or 0 if there is no such payment in database
        """
        return PaymentsDatabase.get_payment_for_subtask(payment_info.subtask_id)

    @staticmethod
    def get_payment_for_subtask(subtask_id):
        try:
            return Payment.get(Payment.subtask == subtask_id).value
        except Payment.DoesNotExist:
            logger.debug("Can't get payment value - payment does not exist")
            return 0

    def add_payment(self, payment_info):
        """ Add new payment to the database.
        :param payment_info:
        """
        Payment.create(subtask=payment_info.subtask_id,
                       payee=payment_info.computer.eth_account.address,
                       value=payment_info.value)

    def change_state(self, subtask_id, state):
        """ Change state for all payments for task_id
        :param str subtask_id: change state of all payments that should be done for computing this task
        :param state: new state
        :return:
        """
        # FIXME: Remove this method
        query = Payment.update(status=state, modified_date=str(datetime.now()))
        query = query.where(Payment.subtask == subtask_id)
        query.execute()

    def get_state(self, payment_info):
        """ Return state of a payment for given task that should be / was made to given node
        :return str|None: return state of payment or none if such payment don't exist in database
        """
        # FIXME: Remove this method
        try:
            return Payment.get(Payment.subtask == payment_info.subtask_id).status
        except Payment.DoesNotExist:
            logger.warning("Payment for subtask {} to node {} does not exist"
                           .format(payment_info.subtask_id, payment_info.computer.key_id))
            return None

    @staticmethod
    def get_newest_payment(num=30):
        """ Return specific number of recently modified payments
        :param num: number of payments to return
        :return:
        """
        query = Payment.select().order_by(Payment.modified_date.desc()).limit(num)
        return query.execute()


class PaymentsKeeper(object):
    """ Keeps information about payments for tasks that should be processed and send or received. """

    def __init__(self):
        """ Create new payments keeper instance"""
        self.db = PaymentsDatabase()

    def get_list_of_all_payments(self):
        # This data is used by UI.
        return [{
            "subtask": payment.subtask,
            "payee": payment.payee,
            "value": payment.value,
            "status": payment.status.value,
            "fee": payment.details.get('fee'),
            "created": datetime_to_timestamp(payment.created_date),
            "modified": datetime_to_timestamp(payment.modified_date)
        } for payment in self.db.get_newest_payment()]

    def finished_subtasks(self, payment_info):
        """ Add new information about finished subtask
        :param PaymentInfo payment_info: full information about payment for given subtask
        """
        self.db.add_payment(payment_info)

    def get_payment(self, subtask_id):
        """
        Get cost of subtasks defined by @subtask_id
        :param subtask_id: Subtask ID
        :return: Cost of the @subtask_id
        """
        return self.db.get_payment_for_subtask(subtask_id)


class PaymentInfo(object):
    """ Full information about payment for a subtask. Include task id, subtask payment information and
    account information about node that has computed this task. """
    def __init__(self, task_id, subtask_id, value, computer):
        self.task_id = task_id
        self.subtask_id = subtask_id
        self.value = value
        self.computer = computer


class AccountInfo(object):
    """ Information about node's payment account """
    # FIXME: Remove this class

    def __init__(self, key_id, port, addr, node_name, node_info):
        self.key_id = key_id
        self.port = port
        self.addr = addr
        self.node_name = node_name
        self.node_info = node_info

    def __eq__(self, other):
        if type(other) is type(self):
            return self.key_id == other.key_id
        return False
