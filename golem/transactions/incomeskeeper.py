import logging
import peewee

from datetime import datetime

from golem.model import ReceivedPayment, db

logger = logging.getLogger(__name__)


class IncomesDatabase(object):
    """ Save and retrieve from database information about incomes
    """

    def get_income_value(self, task_id, node_id):
        """ Retrieve information about recieved value and expected value of a payment that node should receive from
        node_id for computing task_id. If payment for such task doesn't exists write warning and return (0.0, 0.0)
        :param task_id: id of a task that current node computed for node_id
        :param node_id: id of a node that should pay computation
        :return int, int: received value, expected value
        """
        try:
            rp = ReceivedPayment.select(ReceivedPayment.val, ReceivedPayment.expected_val).where(
                self.__same_transaction(task_id, node_id)).get()
            return rp.val, rp.expected_val
        except ReceivedPayment.DoesNotExist:
            logger.warning("Can't get income value - payment does not exist")
            return 0, 0

    def update_income(self, task_id, node_id, value, expected_value, state, add_income=False):
        """ Update information about payment from node_id. If there was not payment from this node for that
        task to current node in database then new income will be added. If there was information about income
        and flag add_income is set to False, then information about income in database will be change. If
        flag add_income is set to True, then value will be added to the value in database and expected value
        will be added to the expected value in database.
        :param str task_id: id of a computed task
        :param str node_id: node that should pay for computed task
        :param int value: received payment
        :param int expected_value: expected income (important for lottery payments)
        :param str state: payment state
        :param bool add_income: if flag is set to True than value and expected value will be added to old
        database data. Otherwise they will replace the old values.
        :return:
        """
        try:
            self.__create_new_income(task_id, node_id, value, expected_value, state)
        except peewee.IntegrityError:
            if add_income:
                self.__add_income(task_id, node_id, value, expected_value, state)
            else:
                self.__change_income(task_id, node_id, value, expected_value, state)

    def change_state(self, task_id, from_node, state):
        """ Change state of payment that node <from_node> should have made for computing task <task_id>
        :param str task_id: computed task
        :param str from_node: node whose payment's state we want to change
        :param state: new state
        """
        query = ReceivedPayment.update(state=state, modified_date=str(datetime.now()))
        query = query.where(self.__same_transaction(task_id, from_node))
        query.execute()

    def get_newest_incomes(self, num=30):
        """ Return <num> recently modfified incomes
        :param int num: number of payments to return
        :return:
        """
        query = ReceivedPayment.select().order_by(ReceivedPayment.modified_date.desc()).limit(num)
        return query.execute()

    def get_state(self, task_id, from_node):
        """ Return state of an income received from <from_node> for computing task <task_id>
        :param str task_id: computed task
        :param str from_node: node who should pay for computed task
        :return str|None: return state of a payment if it's exist in database, otherwise return None
        """
        try:
            return ReceivedPayment.select().where(self.__same_transaction(task_id, from_node)).get().state
        except ReceivedPayment.DoesNotExist:
            return None

    @staticmethod
    def get_awaiting():
        query = ReceivedPayment.select().where(ReceivedPayment.state == IncomesState.waiting)
        query = query.order_by(ReceivedPayment.created_date.desc())
        return query

    def __create_new_income(self, task_id, node_id, value, expected_value, state):
        with db.transaction():
            ReceivedPayment.create(from_node_id=node_id, task=task_id, val=value,
                                   expected_val=expected_value, state=state)

    def __add_income(self, task_id, node_id, value, expected_value, state):
        before = ReceivedPayment.get(self.__same_transaction(task_id, node_id))
        query = ReceivedPayment.update(val=before.val + value,
                                       expected_val=before.expected_val + expected_value,
                                       state=state,
                                       modified_date=str(datetime.now()))
        query = query.where(self.__same_transaction(task_id, node_id))
        query.execute()

    def __change_income(self, task_id, node_id, value, expected_value, state):
        query = ReceivedPayment.update(val=value,
                                       expected_val=expected_value,
                                       state=state,
                                       modified_date=str(datetime.now()))
        query = query.where(self.__same_transaction(task_id, node_id))
        query.execute()

    def __same_transaction(self, task_id, node_id):
        return (ReceivedPayment.from_node_id == node_id) & (ReceivedPayment.task == task_id)


class IncomesKeeper(object):
    """Keeps information about payments received from other nodes
    """

    def __init__(self):
        """ Create new instance of income keeper
        :return:
        """
        self.incomes = {}
        self.db = IncomesDatabase()
        self.load_incomes()

    def load_incomes(self):
        for income in self.db.get_awaiting():
            self.incomes[income.task] = {"task": income.task, "node": income.from_node_id, "value": income.val,
                                         "expected_value": income.expected_val, "state": income.state,
                                         "created": income.created_date}

    def get_list_of_all_incomes(self):
        database_incomes = [{"task": income.task, "node": income.from_node_id, "value": income.val,
                             "expected_value": income.expected_val, "state": income.state} for income in
                            self.db.get_newest_incomes()]
        return database_incomes

    def get_income(self, addr_info, value):
        if value <= 0:
            logger.warning("Wrong income value {}, value should be greater then 0".format(value))
            return None
        finished = []

        def is_not_finished_income(income):
            return income["state"] != IncomesState.finished and self._same_node(addr_info, income["node"])

        not_finished_incomes = filter(is_not_finished_income, self.incomes.values())
        not_finished_incomes.sort(key=lambda x: x["created"])

        for income in not_finished_incomes:
            remain_value = income["expected_value"] - income["value"]
            if value >= remain_value:
                income["value"] += remain_value
                value -= remain_value
                self.finish_task(income["task"])
                finished.append(income["task"])
                if value == 0:
                    return finished
            else:
                income["value"] += value
                self.update_task(income["task"])
                return finished
        return finished

    def finish_task(self, task_id):
        self.incomes[task_id]["state"] = IncomesState.finished
        self.db.update_income(task_id, self.incomes[task_id]["node"], self.incomes[task_id]["value"],
                              self.incomes[task_id]["expected_value"], IncomesState.finished)

    def update_task(self, task_id):
        self.db.update_income(task_id, self.incomes[task_id]["node"], self.incomes[task_id]["value"],
                              self.incomes[task_id]["expected_value"], self.incomes[task_id]["state"])

    def add_income(self, task_id, node_id, reward):
        expected_value = 0
        if task_id in self.incomes:
            if self.incomes[task_id]["state"] != IncomesState.waiting:
                old_reward = self.incomes[task_id]["value"]
                try:
                    reward = int(old_reward) + int(reward)
                except ValueError as err:
                    logger.warning("Wrong reward value {}".format(err))
            expected_value = self.incomes[task_id]["expected_value"]

        self.incomes[task_id] = {"task": task_id, "node": node_id, "value": reward, "expected_value": expected_value,
                                 "state": IncomesState.finished, "created": datetime.now()}
        self.db.update_income(task_id, node_id, reward, expected_value, IncomesState.finished)

    def add_waiting_payment(self, task_id, node_id, expected_value):
        self.incomes[task_id] = {"task": task_id, "node": node_id, "value": 0, "expected_value": expected_value,
                                 "state": IncomesState.waiting, "created": datetime.now()}
        self.db.update_income(task_id, node_id, 0, expected_value, IncomesState.waiting, add_income=True)

    def add_timeouted_payment(self, task_id):
        if task_id not in self.incomes:
            logger.warning("Cannot add payment for task {} to timeouted payments, wasn't waiting "
                           "for this payment".format(task_id))
            return
        self.incomes[task_id]["state"] = IncomesState.timeout
        self.db.change_state(task_id, self.incomes[task_id]["node"], IncomesState.timeout)

    @staticmethod
    def _same_node(addr_info, node_id):
        return addr_info == node_id


class IncomesState(object):
    finished = "Finished"
    waiting = "Waiting"
    timeout = "Not payed"
