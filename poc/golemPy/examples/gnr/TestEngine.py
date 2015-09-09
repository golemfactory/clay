import random
from copy import copy
from multiprocessing import Pool

from PyQt4 import QtCore

from golem.task.TaskBase import Task

class TestEngine(QtCore.QObject):
    ######################
    def __init__(self, logic):

        QtCore.QObject.__init__(self)

        self.logic      = logic
        self.tasks      = {}

        QtCore.QObject.connect(logic, QtCore.SIGNAL("taskStartingRequested(QObject)"), self.__taskStartingRequested)

    #####################
    def addTask(self, task):
        assert isinstance(task, Task)

        self.tasks[ task.header.task_id ] = task

        self.__startComputing()

    #####################
    def __startComputing(self):
        keys = self.tasks.keys()
        r = random.randint(0, len(keys) - 1)

        t = self.tasks[ keys[ r ] ]

        poolSize = 2
        p = Pool(poolSize)

        args = []

        for i in range(poolSize):
            extra_data = t.query_extra_data(1.0)
            args.append([ (t.src_code, extra_data, None) ])

        res = p.map(run_task, args)

        p.start()
        p.join()

    def __taskStartingRequested(self, ts):

        tb = self.logic.renderers[ ts.definition.renderer ].task_builderType("client id here", ts.definition)

        t = Task.build_task(tb)

        self.addTask(t)


#######################
def run_task(self, src_code, extra_data, progress):
    extra_data = copy(extra_data)
    scope = extra_data
    scope[ "taskProgress" ] = progress

    exec src_code in scope
    return scope[ "output" ]

