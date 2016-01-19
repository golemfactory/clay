import logging
import peewee

from datetime import datetime

from golem.model import ReceivedPayment

logger = logging.getLogger(__name__)


class IncomesDatabase(object):
    def __init__(self, database, node_id):
        self.db = database.db
        self.node_id = node_id

    def update_income(self, task_id, node_id, value, expected_value, state, add_income=False):
        try:
            self.__create_new_income(task_id, node_id, value, expected_value, state)
        except peewee.IntegrityError:
            if add_income:
                self.__add_income(task_id, node_id, value, expected_value, state)
            else:
                self.__change_income(task_id, node_id, value, expected_value, state)

    def __create_new_income(self, task_id, node_id, value, expected_value, state):
        with self.db.transaction():
            ReceivedPayment.create(node_id=self.node_id, from_node_id=node_id, task=task_id, val=value,
                                   expected_val=expected_value, state=state)

    def __add_income(self, task_id, node_id, value, expected_value, state):
        query = ReceivedPayment.update(val=ReceivedPayment.val + value,
                                       expected_val=ReceivedPayment.expected_val + expected_value,
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



    def get_income_value(self, task_id, node_id):
        try:
            rp = ReceivedPayment.select(ReceivedPayment.val, ReceivedPayment.expected_val).where(
                self.__same_transaction(task_id, node_id)).get()
            return rp.val, rp.expected_val
        except ReceivedPayment.DoesNotExist:
            logger.warning("Can't get income value - payment does not exist")
            return 0, 0

    def change_state(self, task_id, from_node, state):
        query = ReceivedPayment.update(state=state, modified_date=str(datetime.now()))
        query = query.where(self.__same_transaction(task_id, from_node))
        query.execute()

    def get_newest_incomes(self, num=10):
        return ReceivedPayment.select().where(ReceivedPayment.node_id == self.node_id).execute()

    def __same_transaction(self, task_id, node_id):
        return ReceivedPayment.from_node_id == node_id and ReceivedPayment.node_id == self.node_id \
               and ReceivedPayment.task == task_id


class IncomesKeeper(object):
    def __init__(self, database, node_id):
        self.incomes = {}
        self.db = IncomesDatabase(database, node_id)

    def get_list_of_all_incomes(self):
        database_incomes = [{"task": income.task, "node": income.from_node_id, "value": income.val,
                             "expected_value": income.expected_val, "state": income.state} for income in
                            self.db.get_newest_incomes()]
        return database_incomes

    def add_income(self, task_id, node_id, reward):
        if task_id in self.incomes and self.incomes[task_id]["state"] != IncomesState.waiting:
            old_reward = self.incomes[task_id]["value"]
            try:
                reward = int(old_reward) + int(reward)
            except ValueError as err:
                logger.warning("Wrong reward value {}".format(err))
                return

        self.incomes[task_id] = {"task": task_id, "node": node_id, "value": reward, "expected_value": "?",
                                 "state": IncomesState.finished}
        self.db.update_income(task_id, node_id, reward, 0, IncomesState.finished)

    def add_waiting_payment(self, task_id, node_id):
        self.incomes[task_id] = {"task": task_id, "node": node_id, "value": "?", "expected_value": "?",
                                 "state": IncomesState.waiting}
        self.db.update_income(task_id, node_id, 0, 0, IncomesState.waiting, add_income=True)

    def add_timeouted_payment(self, task_id):
        if task_id not in self.incomes:
            logger.warning("Cannot add payment for task {} to timeouted payments, wasn't waiting "
                           "for this payment".format(task_id))
            return
        self.incomes[task_id]["state"] = IncomesState.timeout
        self.db.change_state(task_id, self.incomes[task_id]["node"], IncomesState.timeout)


class IncomesState(object):
    finished = "Finished"
    waiting = "Waiting"
    timeout = "Not payed"
