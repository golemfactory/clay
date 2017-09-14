import unittest
from unittest.mock import Mock

from devp2p.service import WiredService

from golem.network.p2p.taskprotocol import TaskProtocol
from golem.network.p2p.node import Node
from golem.task.taskbase import ComputeTaskDef


class TestTaskProtocolKeepUnicode(unittest.TestCase):
    task_id = "Gęśla jaźń"
    subtask_id = "Zażółć gęślą jaźń"
    key_id = "0xĄć1ź34þ"
    key = "πœę©ß←↓→óþ"

    def setUp(self):
        self.proto = TaskProtocol(Mock(), Mock(spec=WiredService))

    def check_sedes(self, packet, check, callbacks):
        handler = Mock(side_effect=check)
        callbacks.append(handler)

        self.proto.receive_packet(packet)
        self.assertTrue(handler.called)

    def test_task_request(self):
        packet = self.proto.create_task_request(self.task_id,
                                                0, 0, 0, 0, 0)

        def check_task_id(proto, task_id, **_):
            self.assertEqual(self.task_id, task_id)

        self.check_sedes(packet, check_task_id,
                         self.proto.receive_task_request_callbacks)

    def test_task(self):
        ctd = ComputeTaskDef()
        ctd.task_id = self.task_id
        ctd.subtask_id = self.subtask_id
        ctd.key_id = self.key_id
        ctd.task_owner = Node(key=self.key)

        packet = self.proto.create_task(ctd, 0, 0)

        def check_ctd(proto, definition, **_):
            self.assertEqual(self.task_id, definition.task_id)
            self.assertEqual(self.subtask_id, definition.subtask_id)
            self.assertEqual(self.key_id, definition.key_id)
            self.assertEqual(self.key, definition.task_owner.key)

        self.check_sedes(packet, check_ctd, self.proto.receive_task_callbacks)

    def test_failure(self):
        packet = self.proto.create_failure(self.subtask_id, b'')

        def check(proto, subtask_id, **_):
            self.assertEqual(self.subtask_id, subtask_id)

        self.check_sedes(packet, check,
                         self.proto.receive_failure_callbacks)

    def test_result(self):
        packet = self.proto.create_result(self.subtask_id, 0, self.key_id,
                                          b'', 0, self.key)

        def check(proto, subtask_id, computation_time, resource_hash,
                  resource_secret, resource_options, eth_account):
            self.assertEqual(self.subtask_id, subtask_id)
            self.assertEqual(self.key_id, resource_hash)
            self.assertEqual(self.key, eth_account)

        self.check_sedes(packet, check, self.proto.receive_result_callbacks)

    def test_accept_result(self):
        packet = self.proto.create_accept_result(self.subtask_id, 0)

        def check(proto, subtask_id, **_):
            self.assertEqual(self.subtask_id, subtask_id)

        self.check_sedes(packet, check,
                         self.proto.receive_accept_result_callbacks)

    def test_payment_request(self):
        packet = self.proto.create_payment_request(self.subtask_id)

        def check(proto, subtask_id):
            self.assertEqual(self.subtask_id, subtask_id)

        self.check_sedes(packet, check,
                         self.proto.receive_payment_request_callbacks)

    def test_payment(self):
        packet = self.proto.create_payment(self.subtask_id, self.key_id, 0, b'')

        def check(proto, subtask_id, transaction_id, **_):
            self.assertEqual(self.subtask_id, subtask_id)
            self.assertEqual(self.key_id, transaction_id)

        self.check_sedes(packet, check, self.proto.receive_payment_callbacks)


# Sorry for copy-paste, would prefer parametrized tests but there doesn't seem
# to be any way to do it.
class TestTaskProtocolConvertUnicode(unittest.TestCase):
    task_id = "Gęśla jaźń"
    subtask_id = "Zażółć gęślą jaźń"
    key_id = "0xĄć1ź34þ"
    key = "πœę©ß←↓→óþ"

    def setUp(self):
        self.proto = TaskProtocol(Mock(), Mock(spec=WiredService))

    def check_sedes(self, packet, check, callbacks):
        handler = Mock(side_effect=check)
        callbacks.append(handler)

        self.proto.receive_packet(packet)
        self.assertTrue(handler.called)

    def test_task_request(self):
        packet = self.proto.create_task_request(self.task_id.encode('utf_8'),
                                                0, 0, 0, 0, 0)

        def check_task_id(proto, task_id, **_):
            self.assertEqual(self.task_id, task_id)

        self.check_sedes(packet, check_task_id,
                         self.proto.receive_task_request_callbacks)

    def test_task(self):
        ctd = ComputeTaskDef()
        ctd.task_id = self.task_id.encode('utf_8')
        ctd.subtask_id = self.subtask_id.encode('utf_8')
        ctd.key_id = self.key_id.encode('utf_8')
        ctd.task_owner = Node(key=self.key.encode('utf_8'))

        packet = self.proto.create_task(ctd, 0, 0)

        def check_ctd(proto, definition, **_):
            self.assertEqual(self.task_id, definition.task_id)
            self.assertEqual(self.subtask_id, definition.subtask_id)
            self.assertEqual(self.key_id, definition.key_id)
            self.assertEqual(self.key, definition.task_owner.key)

        self.check_sedes(packet, check_ctd, self.proto.receive_task_callbacks)

    def test_failure(self):
        packet = self.proto.create_failure(self.subtask_id.encode('utf_8'), b'')

        def check(proto, subtask_id, **_):
            self.assertEqual(self.subtask_id, subtask_id)

        self.check_sedes(packet, check,
                         self.proto.receive_failure_callbacks)

    def test_result(self):
        packet = self.proto.create_result(self.subtask_id.encode('utf_8'), 0,
                                          self.key_id.encode('utf_8'),
                                          b'', 0, self.key.encode('utf_8'))

        def check(proto, subtask_id, computation_time, resource_hash,
                  resource_secret, resource_options, eth_account):
            self.assertEqual(self.subtask_id, subtask_id)
            self.assertEqual(self.key_id, resource_hash)
            self.assertEqual(self.key, eth_account)

        self.check_sedes(packet, check, self.proto.receive_result_callbacks)

    def test_accept_result(self):
        packet = self.proto.create_accept_result(
            self.subtask_id.encode('utf_8'), 0)

        def check(proto, subtask_id, **_):
            self.assertEqual(self.subtask_id, subtask_id)

        self.check_sedes(packet, check,
                         self.proto.receive_accept_result_callbacks)

    def test_payment_request(self):
        packet = self.proto.create_payment_request(
            self.subtask_id.encode('utf_8'))

        def check(proto, subtask_id):
            self.assertEqual(self.subtask_id, subtask_id)

        self.check_sedes(packet, check,
                         self.proto.receive_payment_request_callbacks)

    def test_payment(self):
        packet = self.proto.create_payment(self.subtask_id.encode('utf_8'),
                                           self.key_id.encode('utf_8'), 0, b'')

        def check(proto, subtask_id, transaction_id, **_):
            self.assertEqual(self.subtask_id, subtask_id)
            self.assertEqual(self.key_id, transaction_id)

        self.check_sedes(packet, check, self.proto.receive_payment_callbacks)
