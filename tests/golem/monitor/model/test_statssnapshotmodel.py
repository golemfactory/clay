import jsonpickle as json
from unittest import TestCase
from uuid import uuid4

from golem.diag.service import DiagnosticsOutputFormat
from golem.diag.vm import VMDiagnosticsProvider
from golem.monitor.model.statssnapshotmodel import StatsSnapshotModel, VMSnapshotModel, P2PSnapshotModel


class TestsStatsSnapshotModel(TestCase):
    def test_init(self):
        cliid = uuid4().get_hex()
        sessid = uuid4().get_hex()
        model = StatsSnapshotModel(cliid, sessid, 30, 10, 480, 3, 2)
        assert isinstance(model, StatsSnapshotModel)
        assert model.cliid == cliid
        assert model.sessid == sessid
        assert model.known_tasks == 30
        assert model.supported_tasks == 10
        assert model.computed_tasks == 480
        assert model.tasks_with_errors == 3
        assert model.tasks_with_timeout == 2
        assert model.type == "Stats"
        assert type(model.dict_repr()) is dict
        json.dumps(model.dict_repr())


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

