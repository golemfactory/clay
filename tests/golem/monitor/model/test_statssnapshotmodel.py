import json
import random
import unittest.mock as mock
from unittest import TestCase
from uuid import uuid4

from golem.diag.service import DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.monitor.model.modelbase import BasicModel
from golem.monitor.model.statssnapshotmodel import VMSnapshotModel, \
    P2PSnapshotModel, RequestorAggregateStatsModel, ProviderStatsModel
from golem.monitor.test_helper import MonitorTestBaseClass
from golem.task.taskproviderstats import ProviderStats
from golem.task.taskrequestorstats import AggregateTaskStats


class TestStatsSnapshotModel(MonitorTestBaseClass):
    maxDiff = None

    @mock.patch('requests.post')
    @mock.patch('json.dumps')
    def test_channel(self, mock_dumps, *_):
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
            return (None, stats_d[name])
        stats_mock.get_stats = _get_stats

        self.loop.run_until_complete(
            self.monitor.on_stats_snapshot(
                known_tasks=known_tasks,
                supported_tasks=supported_tasks,
                stats=stats_mock,
            ),
        )
        expected = {
            'proto_ver': 1,
            'data': {
                'id': mock.ANY,
                'cliid': mock.ANY,
                'sessid': mock.ANY,
                'timestamp': mock.ANY,
                'type': 'Stats',
                'known_tasks': known_tasks,
                'supported_tasks': supported_tasks,
            },
        }
        mock_dumps.assert_called_once()
        self.assertCountEqual(expected, mock_dumps.call_args[0][0])

class TestP2PSnapshotModel(TestCase):
    def test_init(self):
        cliid = str(uuid4())
        sessid = str(uuid4())
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
        cliid = str(uuid4())
        sessid = str(uuid4())
        vmsnapshot = VMDiagnosticsProvider().get_diagnostics(DiagnosticsOutputFormat.data)
        model = VMSnapshotModel(cliid, sessid, vmsnapshot)
        assert isinstance(model, VMSnapshotModel)
        assert model.cliid == cliid
        assert model.sessid == sessid
        assert model.vm_snapshot == vmsnapshot
        assert model.type == "VMSnapshot"
        assert type(model.dict_repr()) is dict
        json.dumps(model.dict_repr())


class TestRequestorAggregateStatsModel(TestCase):
    def test_init(self):
        cliid = str(uuid4())
        sessid = str(uuid4())
        stats = AggregateTaskStats()
        meta_data = BasicModel("NotRequestorAggregateStats", cliid, sessid)
        model = RequestorAggregateStatsModel(meta_data, stats)

        assert model.cliid == cliid
        assert model.sessid == sessid
        assert model.type == "RequestorAggregateStats"
        assert isinstance(model.dict_repr(), dict)

        for key in vars(stats):
            assert hasattr(model, key)
        json.dumps(model.dict_repr())


class TestProviderStatsModel(TestCase):
    def test_init(self):
        cliid = str(uuid4())
        sessid = str(uuid4())
        stats = ProviderStats()
        meta_data = BasicModel("NotProviderStats", cliid, sessid)
        model = ProviderStatsModel(meta_data, stats)

        assert model.cliid == cliid
        assert model.sessid == sessid
        assert model.type == "ProviderStats"
        assert isinstance(model.dict_repr(), dict)

        for key in vars(stats):
            assert hasattr(model, key)
        json.dumps(model.dict_repr())
