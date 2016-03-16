import logging
import random
import time
import datetime
from taskbase import TaskHeader

logger = logging.getLogger(__name__)


class TaskKeeper(object):
    def __init__(self, environments_manager, min_price=0.0, app_version=1.0, remove_task_timeout=240.0,
                 verification_timeout=3600):
        self.task_headers = {}
        self.supported_tasks = []
        self.removed_tasks = {}
        self.active_tasks = {}
        self.active_requests = {}
        self.completed = {}
        self.declared_prices = {}
        self.min_price = min_price
        self.app_version = app_version

        self.verification_timeout = verification_timeout
        self.removed_task_timeout = remove_task_timeout
        self.environments_manager = environments_manager

    def is_supported(self, th_dict_repr):
        supported = self.check_environment(th_dict_repr)
        supported = supported and self.check_price(th_dict_repr)
        return supported and self.check_version(th_dict_repr)

    def get_task(self, price):
        if len(self.supported_tasks) > 0:
            tn = random.randrange(0, len(self.supported_tasks))
            task_id = self.supported_tasks[tn]
            theader = self.task_headers[task_id]
            if task_id in self.active_requests:
                self.active_requests[task_id] += 1
            else:
                self.active_tasks[task_id] = {'header': theader, 'price': price}
                self.active_requests[task_id] = 1
            return theader
        else:
            return None

    def check_environment(self, th_dict_repr):
        env = th_dict_repr.get("environment")
        if not env:
            return False
        if not self.environments_manager.supported(env):
            return False
        return self.environments_manager.accept_tasks(env)

    def check_price(self, th_dict_repr):
        return th_dict_repr.get("max_price") >= self.min_price

    def check_version(self, th_dict_repr):
        min_v = th_dict_repr.get("min_version")
        if not min_v:
            return True
        try:
            supported = float(self.app_version) >= float(min_v)
            return supported
        except ValueError:
            logger.error(
                "Wrong app version - app version {}, required version {}".format(
                    self.app_version,
                    min_v
                )
            )
            return False

    def get_all_tasks(self):
        return self.task_headers.values()

    def change_config(self, config_desc):
        if config_desc.min_price == self.min_price:
            return
        self.min_price = config_desc.min_price
        self.supported_tasks = []
        for id_, th in self.task_headers.iteritems():
            if self.is_supported(th.__dict__):
                self.supported_tasks.append(id_)

    def add_task_header(self, th_dict_repr):
        try:
            id_ = th_dict_repr["id"]
            if id_ not in self.task_headers.keys():  # don't have it
                if id_ not in self.removed_tasks.keys():  # not removed recently
                    is_supported = self.is_supported(th_dict_repr)
                    logger.info("Adding task {} is_supported={}".format(id_, is_supported))
                    self.task_headers[id_] = TaskHeader(node_name=th_dict_repr["node_name"],
                                                        task_id=id_,
                                                        task_owner_address=th_dict_repr["address"],
                                                        task_owner_port=th_dict_repr["port"],
                                                        task_owner_key_id=th_dict_repr["key_id"],
                                                        environment=th_dict_repr["environment"],
                                                        task_owner=th_dict_repr["task_owner"],
                                                        ttl=th_dict_repr["ttl"],
                                                        subtask_timeout=th_dict_repr["subtask_timeout"],
                                                        max_price=th_dict_repr["max_price"])
                    if is_supported:
                        self.supported_tasks.append(id_)
            return True
        except (KeyError, TypeError) as err:
            logger.error("Wrong task header received {}".format(err))
            return False

    def remove_task_header(self, task_id):
        if task_id in self.task_headers:
            del self.task_headers[task_id]
        if task_id in self.supported_tasks:
            self.supported_tasks.remove(task_id)
        self.removed_tasks[task_id] = time.time()
        if task_id in self.active_requests and self.active_requests[task_id] <= 0:
            self.__del_active_task(task_id)

    def get_subtask_ttl(self, task_id):
        if task_id in self.task_headers:
            return self.task_headers[task_id].subtask_timeout

    def receive_task_verification(self, task_id):
        if task_id not in self.active_tasks:
            logger.warning("Wasn't waiting for verification result for {}").format(task_id)
            return
        self.active_requests[task_id] -= 1
        if self.active_requests[task_id] <= 0 and task_id not in self.task_headers:
            self.__del_active_task(task_id)

    def get_task_id_for_subtask(self, subtask_id):
        if subtask_id not in self.completed:
            return None
        return self.completed[subtask_id][0]

    def is_waiting_for_subtask(self, subtask_id):
        return self.completed.get(subtask_id) is not None

    def is_waiting_for_task(self, task_id):
        for v in self.completed.itervalues():
            if v[0] == task_id:
                return True
        return False

    def remove_completed(self, task_id=None, subtask_id=None):
        if task_id:
            subtasks = [sub_id for sub_id, val in self.completed.iteritems() if val[0] == task_id]
            for sub_id in subtasks:
                del self.completed[sub_id]
        if subtask_id:
            del self.completed[subtask_id]

    def remove_old_tasks(self):
        for t in self.task_headers.values():
            cur_time = time.time()
            t.ttl = t.ttl - (cur_time - t.last_checking)
            t.last_checking = cur_time
            if t.ttl <= 0:
                logger.warning("Task {} dies".format(t.task_id))
                self.remove_task_header(t.task_id)

        for task_id, remove_time in self.removed_tasks.items():
            cur_time = time.time()
            if cur_time - remove_time > self.removed_task_timeout:
                del self.removed_tasks[task_id]

    def request_failure(self, task_id):
        if task_id in self.active_requests:
            self.active_requests[task_id] -= 1
        self.remove_task_header(task_id)

    def get_receiver_for_task_verification_result(self, task_id):
        if task_id not in self.active_tasks:
            return None
        return self.active_tasks[task_id]['header'].task_owner_key_id

    def add_completed(self, subtask_id, task_id, computing_time):
        now = datetime.datetime.now()
        self.completed[subtask_id] = [task_id, now, self.__count_deadline(now)]
        tk = self.active_tasks.get(task_id)
        if tk:
            return tk['price'] * computing_time
        else:
            logger.error("Unknown price for task {}".format(task_id))
            return 0

    def check_payments(self):
        # TODO Save unpaid tasks somewhere else
        now = datetime.datetime.now()
        after_deadline = []
        for subtask_id, [task_id, task_date, deadline] in self.completed.items():
            if deadline < now:
                after_deadline.append(task_id)
                del self.completed[subtask_id]
        return after_deadline

    def __count_deadline(self, date):  # FIXME Cos zdecydowanie bardziej zaawansowanego i moze dopasowanego do kwoty
        return datetime.datetime.fromtimestamp(time.time() + self.verification_timeout)

    def __del_active_task(self, task_id):
        del self.active_tasks[task_id]
        del self.active_requests[task_id]
