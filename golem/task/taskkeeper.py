import logging
import random
import time
import datetime
from taskbase import TaskHeader

logger = logging.getLogger(__name__)


class TaskKeeper(object):
    def __init__(self, remove_task_timeout=240.0, verification_timeout=3600):
        self.task_headers = {}
        self.supported_tasks = []
        self.removed_tasks = {}
        self.active_tasks = {}
        self.active_requests = {}
        self.waiting_for_verification = {}

        self.verification_timeout = verification_timeout
        self.removed_task_timeout = remove_task_timeout

    def get_task(self):
        if len(self.supported_tasks) > 0:
            tn = random.randrange(0, len(self.supported_tasks))
            task_id = self.supported_tasks[tn]
            theader = self.task_headers[task_id]
            if task_id in self.active_requests:
                self.active_requests[task_id] += 1
            else:
                self.active_tasks[task_id] = theader
                self.active_requests[task_id] = 1
            return theader
        else:
            return None

    def get_all_tasks(self):
        return self.task_headers.values()

    def add_task_header(self, th_dict_repr, is_supported):
        try:
            id_ = th_dict_repr["id"]
            if id_ not in self.task_headers.keys():  # don't have it
                if id_ not in self.removed_tasks.keys():  # not removed recently
                    logger.info("Adding task {} is_supported={}".format(id_, is_supported))
                    self.task_headers[id_] = TaskHeader(th_dict_repr["node_name"], id_, th_dict_repr["address"],
                                                        th_dict_repr["port"], th_dict_repr["key_id"],
                                                        th_dict_repr["environment"], th_dict_repr["task_owner"],
                                                        th_dict_repr["ttl"], th_dict_repr["subtask_timeout"])
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

    def get_waiting_for_verification_task_id(self, subtask_id):
        if subtask_id not in self.waiting_for_verification:
            return None
        return self.waiting_for_verification[subtask_id][0]

    def is_waiting_for_task(self, task_id):
        for v in self.waiting_for_verification.itervalues():
            if v[0] == task_id:
                return True
        return False

    def remove_waiting_for_verification(self, task_id):
        subtasks = [subId for subId, val in self.waiting_for_verification.iteritems() if val[0] == task_id]
        for subtask_id in subtasks:
            del self.waiting_for_verification[subtask_id]

    def remove_waiting_for_verification_task_id(self, subtask_id):
        if subtask_id in self.waiting_for_verification:
            del self.waiting_for_verification[subtask_id]

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
        return self.active_tasks[task_id].owner_key_id

    def add_to_verification(self, subtask_id, task_id):
        now = datetime.datetime.now()
        self.waiting_for_verification[subtask_id] = [task_id, now, self.__count_deadline(now)]

    def check_payments(self):
        now = datetime.datetime.now()
        after_deadline = []
        for subtask_id, [task_id, task_date, deadline] in self.waiting_for_verification.items():
            if deadline < now:
                after_deadline.append(task_id)
                del self.waiting_for_verification[subtask_id]
        return after_deadline

    def __count_deadline(self, date):  # FIXME Cos zdecydowanie bardziej zaawansowanego i moze dopasowanego do kwoty
        return datetime.datetime.fromtimestamp(time.time() + self.verification_timeout)

    def __del_active_task(self, task_id):
        del self.active_tasks[task_id]
        del self.active_requests[task_id]
