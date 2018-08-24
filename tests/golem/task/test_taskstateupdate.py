import copy
import threading
from unittest import TestCase

import enforce
from golem_messages import message

from golem.task.taskstateupdate import StateUpdateResponse, StateUpdateInfo, \
    StateUpdateData

enforce.config({'groups': {'set': {'taskstateupdate': True}}})


class TestStateUpdateResponse(TestCase):
    def test_init(self):
        with self.assertRaises(enforce.exceptions.RuntimeTypeError):
            _ = StateUpdateResponse(None, None)
        event = threading.Event()
        _ = StateUpdateResponse(event, {})

        with self.assertRaises(enforce.exceptions.RuntimeTypeError):
            _ = StateUpdateResponse(event, 1)

class TestStateUpdateInfo(TestCase):
    FIELDS = ["task_id", "subtask_id", "state_update_id"]

    def test_init(self):
        kwargs = {f: f"{f}abc" for f in self.FIELDS}

        sui = StateUpdateInfo(**kwargs)
        assert all(getattr(sui, k) == f"{k}abc" for k in self.FIELDS)

        for wrong_type in self.FIELDS:
            kwargs_copy = kwargs.copy()

            kwargs_copy[wrong_type] = 1
            with self.assertRaises(enforce.exceptions.RuntimeTypeError):
                _ = StateUpdateInfo(**kwargs_copy)
            kwargs_copy[wrong_type] = None
            with self.assertRaises(enforce.exceptions.RuntimeTypeError):
                _ = StateUpdateInfo(**kwargs_copy)

    def test_from_state_update_msg(self):
        msg = message.tasks.StateUpdate()

        msg.task_id = "abc"
        msg.subtask_id = "def"
        msg.state_update_id = "ghi"

        resp = StateUpdateInfo.from_state_update_msg(msg)
        assert isinstance(resp, StateUpdateInfo) and \
               resp.task_id == msg.task_id and \
               resp.subtask_id == msg.subtask_id and \
               resp.state_update_id == msg.state_update_id

    def test_from_dict(self):
        task_id = "abc"
        subtask_id = "def"
        state_update_id = "ghi"

        with self.assertRaises(enforce.exceptions.RuntimeTypeError):
            StateUpdateInfo.from_dict(["aaa"])

        d1 = {"task_id": task_id,
              "subtask_id": subtask_id,
              "state_update_id": state_update_id
              }
        resp = StateUpdateInfo.from_dict(d1)
        assert resp.task_id == task_id and \
               resp.subtask_id == subtask_id and \
               resp.state_update_id == state_update_id

        for missing in d1.keys():
            d2 = d1.copy()
            del d2[missing]
            with self.assertRaises(KeyError):
                StateUpdateInfo.from_dict(d2)

    def test_eq(self):
        some_info1 = StateUpdateInfo("aaa", "bbb", "ccc")
        some_info2 = StateUpdateInfo("aaa", "bbb", "ccc")
        assert some_info1 == some_info2

        for different in self.FIELDS:
            some_info3 = copy.copy(some_info1)
            some_info3.__dict__[different] = "different"
            assert some_info1 != some_info3

    def test_hash(self):
        some_info1 = StateUpdateInfo("aaa", "bbb", "ccc")
        some_info2 = StateUpdateInfo("aaa", "bbb", "ccc")
        assert hash(some_info1) == hash(some_info2)

        for different in self.FIELDS:
            some_info3 = copy.copy(some_info1)
            some_info3.__dict__[different] = "different"
            assert hash(some_info1) != hash(some_info3)


class TestStateUpdateData(TestCase):
    FIELDS = ["info", "data"]

    kwargs = {"info": StateUpdateInfo("aa", "bb", "cc"),
              "data": {"abc": "def"}
              }

    def test_init(self):
        res = StateUpdateData(**self.kwargs)
        assert res.info == self.kwargs["info"] and res.data == self.kwargs[
            "data"]

        for wrong_type in self.FIELDS:
            kwargs_copy = self.kwargs.copy()
            kwargs_copy[wrong_type] = 1
            with self.assertRaises(enforce.exceptions.RuntimeTypeError):
                StateUpdateData(**kwargs_copy)
            kwargs_copy[wrong_type] = None
            with self.assertRaises(enforce.exceptions.RuntimeTypeError):
                StateUpdateData(**kwargs_copy)

    def test_to_dict(self):
        res = StateUpdateData(**self.kwargs).to_dict()
        assert res == {"task_id": self.kwargs["info"].task_id,
                       "subtask_id": self.kwargs["info"].subtask_id,
                       "state_update_id": self.kwargs["info"].state_update_id,
                       "data": self.kwargs["data"]}

    def test_from_dict(self):
        d1 = {"info": {"task_id": "aaa",
                       "subtask_id": "bbb",
                       "state_update_id": "ccc"
                       },
              "data": {"aaa": "bbb"}}
        resp = StateUpdateData.from_dict(d1)
        assert resp.data == d1["data"] and \
               resp.info == StateUpdateInfo.from_dict(d1["info"])

        for key in d1.keys():
            d2 = d1.copy()
            del d2[key]
            with self.assertRaises(KeyError):
                StateUpdateData.from_dict(d2)

            d2[key] = 1
            with self.assertRaises(enforce.exceptions.RuntimeTypeError):
                StateUpdateData.from_dict(d2)

            d2[key] = None
            with self.assertRaises(enforce.exceptions.RuntimeTypeError):
                StateUpdateData.from_dict(d2)