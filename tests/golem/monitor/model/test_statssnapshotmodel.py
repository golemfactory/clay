import jsonpickle as json
import mock
from pydispatch import dispatcher
import random
from unittest import TestCase
from uuid import uuid4

from golem.diag.service import DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.monitor.model.statssnapshotmodel import VMSnapshotModel, P2PSnapshotModel
from golem.monitor.test_helper import MonitorTestBaseClass

class TestStatsSnapshotModel(MonitorTestBaseClass):
    def test_channel(self):
        known_tasks = random.randint(0, 10000)
        supported_tasks = random.randint(0, known_tasks)
        stats_mock = mock.MagicMock()
        stats_d = {
            'computed_tasks': random.randint(0, 10**10),
            'tasks_with_errors': random.randint(0, 10**2),
            'tasks_with_timeout': random.randint(0, 10**2),
            'tasks_requested': random.randint(0, 10**11),
        }
        def _get_stats(name):
            return (stats_d[name], None)
        stats_mock.get_stats = _get_stats

        with mock.patch('golem.monitor.monitor.SenderThread.send') as mock_send:
            dispatcher.send(
                signal='golem.monitor',
                event='stats_snapshot',
                known_tasks=known_tasks,
                supported_tasks=supported_tasks,
                stats=stats_mock,
            )
            self.assertEquals(mock_send.call_count, 1)
            result = mock_send.call_args[0][0].dict_repr()
            for key in ('cliid', 'sessid', 'timestamp'):
                del result[key]
            expected = {
                'type': 'Stats',
                'known_tasks': known_tasks,
                'supported_tasks': supported_tasks,
            }
            expected.update(stats_d)
            self.assertEquals(expected, result)

class TestP2PSnapshotModel(TestCase):
    def test_init(self):
        cliid = uuid4().get_hex()
        sessid = uuid4().get_hex()
        p2psnapshot = [{"key_id": "peer1", "port": 1030, "host": "10.10.10.10"},
                       {"key_id": "peer1", "port": 1111, "host": "192.19.19.19"}]
        model = P2PSnapshotModel(cliid, sessid, p2psnapshot)
        assert isinstance(model, P2PSnapshotModel)
        assert model.cliid == cliid
        assert model.sessid == sessid
        assert model.p2p_snapshot == p2psnapshot
        assert model.type == "P2PSnapshot"
        assert type(model.dict_repr()) is dict
        json.dumps(model.dict_repr())


class TestVMnapshotModel(TestCase):
    def test_init(self):
        cliid = uuid4().get_hex()
        sessid = uuid4().get_hex()
        vmsnapshot = VMDiagnosticsProvider().get_diagnostics(DiagnosticsOutputFormat.data)
        model = VMSnapshotModel(cliid, sessid, vmsnapshot)
        assert isinstance(model, VMSnapshotModel)
        assert model.cliid == cliid
        assert model.sessid == sessid
        assert model.vm_snapshot == vmsnapshot
        assert model.type == "VMSnapshot"
        assert type(model.dict_repr()) is dict
        json.dumps(model.dict_repr())

