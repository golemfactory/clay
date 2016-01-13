import logging

logger = logging.getLogger(__name__)


#  TODO
class IncomesKeeper(object):
    def __init__(self):
        self.incomes = {}

    def get_list_of_all_incomes(self):
        return self.incomes.values()

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

    def add_waiting_payment(self, task_id, node_id):
        self.incomes[task_id] = {"task": task_id, "node": node_id, "value": "?", "expected_value": "?",
                                 "state": IncomesState.waiting}

    def add_timeouted_payment(self, task_id):
        if task_id not in self.incomes:
            logger.warning("Cannot add payment for task {} to timeouted payments, wasn't waiting "
                           "for this payment".format(task_id))
            return
        self.incomes[task_id]["state"] = IncomesState.timeout


class IncomesState(object):
    finished = "Finished"
    waiting = "Waiting"
    timeout = "Not payed"
