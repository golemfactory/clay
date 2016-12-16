import jsonpickle as json
from unittest import TestCase
from uuid import uuid4

from golem.monitor.model.taskcomputersnapshotmodel import TaskComputerSnapshotModel


class TestTaskComputerSnapshotModel(TestCase):
    def test_init(self):
        cliid = uuid4().get_hex()
        sessid = uuid4().get_hex()
        model = TaskComputerSnapshotModel(cliid, sessid, False, True, False, True, ["task_1"])
        assert isinstance(model, TaskComputerSnapshotModel)
        assert model.cliid == cliid
        assert model.sessid == sessid
        assert not model.waiting_for_task
        assert model.counting_task
        assert not model.task_requested
        assert model.compute_task
        assert model.assigned_subtasks == ["task_1"]
        assert model.type == "TaskComputer"
        assert type(model.dict_repr()) is dict
        json.dumps(model.dict_repr())
