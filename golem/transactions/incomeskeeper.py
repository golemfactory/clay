

#  TODO
class IncomesKeeper(object):
    def __init__(self):
        self.incomes = []

    def get_list_of_all_incomes(self):
        return self.incomes

    def add_income(self, task_id, node_id, reward):
        self.incomes.append({"task": task_id, "node": node_id, "value": reward, "expected_value": "?",
                             "state": IncomesState.finished})


class IncomesState(object):
    finished = "Finished"
