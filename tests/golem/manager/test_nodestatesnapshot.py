from datetime import datetime
from unittest import TestCase

from golem.manager.nodestatesnapshot import TaskChunkStateSnapshot, LocalTaskStateSnapshot, NodeStateSnapshot


class TestTaskChunkStateSnapshot(TestCase):
    def test_state(self):
        tcss = TaskChunkStateSnapshot("xxyyzz", 1032, 240, 0.8, "some work")
        assert isinstance(tcss, TaskChunkStateSnapshot)
        assert tcss.chunk_id == "xxyyzz"
        assert tcss.cpu_power == 1032
        assert tcss.est_time_left == 240
        assert tcss.progress == 0.8
        assert tcss.chunk_short_desc == "some work"

        assert tcss.get_chunk_id() == "xxyyzz"
        assert tcss.get_cpu_power() == 1032
        assert tcss.get_estimated_time_left() == 240
        assert tcss.get_progress() == 0.8
        assert tcss.get_chunk_short_descr() == "some work"


class TestLocalTaskStateSnapshot(TestCase):
    def test_state(self):
        ltss = LocalTaskStateSnapshot("xyz", 1000, 200, 0.8, "very big task")
        assert isinstance(ltss, LocalTaskStateSnapshot)
        assert ltss.task_id == "xyz"
        assert ltss.total_tasks == 1000
        assert ltss.active_tasks == 200
        assert ltss.progress == 0.8
        assert ltss.task_short_desc == "very big task"

        assert ltss.get_task_id() == "xyz"
        assert ltss.get_total_tasks() == 1000
        assert ltss.get_active_tasks() == 200
        assert ltss.get_progress() == 0.8
        assert ltss.get_task_short_desc() == "very big task"


class TestNodeStateSnapshot(TestCase):
    def test_node_state_snapshot(self):
        nss = NodeStateSnapshot()
        nss2 = NodeStateSnapshot(True, "ABC", 5, 8, "10.10.10.10", 1024)
        nss2.last_network_messages.append("last network message")
        nss2.last_task_messages.append("last task message")
        nss2.task_chunk_state["xxyyzz"] = "task chunk state"
        nss2.local_task_state["xyz"] = "local task state"
        assert isinstance(nss, NodeStateSnapshot)
        assert nss.uid == 0
        assert nss.timestamp <= datetime.utcnow()
        assert nss.endpoint_addr == ""
        assert nss.endpoint_port == ""
        assert nss.peers_num == 0
        assert nss.tasks_num == 0
        assert nss.last_network_messages == []
        assert nss.last_task_messages == []
        assert nss.task_chunk_state == {}
        assert nss.local_task_state == {}
        assert nss.running
        assert isinstance(nss2, NodeStateSnapshot)
        assert nss2.uid == "ABC"
        assert nss2.timestamp <= datetime.utcnow()
        assert nss2.endpoint_addr == "10.10.10.10"
        assert nss2.endpoint_port == 1024
        assert nss2.peers_num == 5
        assert nss2.tasks_num == 8
        assert nss2.last_network_messages == ["last network message"]
        assert nss2.last_task_messages == ["last task message"]
        assert nss2.task_chunk_state == {"xxyyzz": "task chunk state"}
        assert nss2.local_task_state == {"xyz": "local task state"}
        assert nss2.running

        assert nss.is_running()
        assert nss2.get_uid() == "ABC"
        assert isinstance(nss.get_formatted_timestamp(), str)
        assert nss2.get_endpoint_addr() == "10.10.10.10"
        assert nss2.get_endpoint_port() == 1024
        assert nss2.get_peers_num() == 5
        assert nss2.get_tasks_num() == 8
        assert nss2.get_last_network_messages() == ["last network message"]
        assert nss.get_last_task_messages() == []
        assert nss2.get_task_chunk_state_snapshot() == {"xxyyzz": "task chunk state"}
        assert nss.get_local_task_state_snapshot() == {}

        assert str(nss2) == "ABC ----- \npeers count: 5\ntasks count: 8\nlast net communication: " \
                            "['last network message']\nlast task communication: ['last task message']"
