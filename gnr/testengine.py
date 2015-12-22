import random
from copy import copy
from multiprocessing import Pool
from PyQt4 import QtCore
from golem.task.taskbase import Task


class TestEngine(QtCore.QObject):
    def __init__(self, logic):
        QtCore.QObject.__init__(self)

        self.logic = logic
        self.tasks = {}

        QtCore.QObject.connect(logic, QtCore.SIGNAL("taskStartingRequested(QObject)"), self.__task_starting_requested)

    def add_task(self, task):
        assert isinstance(task, Task)

        self.tasks[task.header.task_id] = task

        self.__start_computing()

    def __start_computing(self):
        keys = self.tasks.keys()
        r = random.randint(0, len(keys) - 1)

        t = self.tasks[keys[r]]

        pool_size = 2
        p = Pool(pool_size)

        args = []

        for i in range(pool_size):
            extra_data = t.query_extra_data(1.0)
            args.append([(t.src_code, extra_data, None)])

        res = p.map(run_task, args)

        p.start()
        p.join()

    def __task_starting_requested(self, ts):
        tb = self.logic.renderers[ts.definition.renderer].task_builder_type("client id here", ts.definition)

        t = Task.build_task(tb)

        self.add_task(t)


def run_task(self, src_code, extra_data, progress):
    extra_data = copy(extra_data)
    scope = extra_data
    scope["taskProgress"] = progress

    exec src_code in scope
    return scope["output"]
