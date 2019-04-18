import pathlib
import time
import unittest
from unittest import mock

import faker
from golem_messages import message
from golem_messages import factories as msg_factories

from golem import model
from golem import testutils
from golem.core import keysauth
from golem.network.hyperdrive.client import HyperdriveClientOptions
from golem.task.server import helpers
from tests import factories

fake = faker.Faker()


@mock.patch(
    'golem.network.history.MessageHistoryService.get_sync_as_message',
)
@mock.patch("golem.network.transport.msg_queue.put")
class TestSendReportComputedTask(testutils.TempDirFixture):
    def setUp(self):
        super().setUp()
        self.wtr = factories.taskserver.WaitingTaskResultFactory()

        self.task_server = mock.MagicMock()
        self.task_server.cur_port = 31337
        self.task_server.node = msg_factories.datastructures.p2p.Node(
            node_name=fake.name(),
        )
        self.task_server.get_key_id.return_value = 'key id'
        self.task_server.keys_auth = keysauth.KeysAuth(
            self.path,
            'filename',
            '',
        )
        self.task_server.get_share_options.return_value =\
            HyperdriveClientOptions(
                "CLI id",
                0.3,
            )

        self.ttc = msg_factories.tasks.TaskToComputeFactory(
            task_id=self.wtr.task_id,
            subtask_id=self.wtr.subtask_id,
            compute_task_def__deadline=int(time.time()) + 3600,
        )

    def assert_submit_task_message(self, subtask_id, wtr):
        submit_mock = self.task_server.client.concent_service\
            .submit_task_message
        submit_mock.assert_called_once_with(
            subtask_id,
            mock.ANY,
        )

        msg = submit_mock.call_args[0][1]
        self.assertEqual(msg.result_hash, 'sha1:' + wtr.package_sha1)

    @mock.patch(
        'golem.network.history.add',
    )
    def test_basic(self, add_mock, put_mock, get_mock, *_):
        get_mock.return_value = self.ttc
        helpers.send_report_computed_task(
            self.task_server,
            self.wtr,
        )

        put_mock.assert_called_once()
        node_id, rct = put_mock.call_args[0]

        self.assertEqual(node_id, self.wtr.owner.key)
        self.assertIsInstance(rct, message.tasks.ReportComputedTask)
        self.assertEqual(rct.subtask_id, self.wtr.subtask_id)
        self.assertEqual(rct.node_name, self.task_server.node.node_name)
        self.assertEqual(rct.address, self.task_server.node.prv_addr)
        self.assertEqual(rct.port, self.task_server.cur_port)
        self.assertEqual(rct.extra_data, [])
        self.assertEqual(rct.node_info, self.task_server.node.to_dict())
        self.assertEqual(rct.package_hash, 'sha1:' + self.wtr.package_sha1)
        self.assertEqual(rct.multihash, self.wtr.result_hash)
        self.assertEqual(rct.secret, self.wtr.result_secret)

        add_mock.assert_called_once_with(
            msg=mock.ANY,
            node_id=self.wtr.owner.key,
            local_role=model.Actor.Provider,
            remote_role=model.Actor.Requestor,
        )

    def test_concent_no_message(self, _put_mock, get_mock, *_):
        get_mock.return_value = self.ttc
        helpers.send_report_computed_task(
            self.task_server,
            self.wtr,
        )
        self.task_server.concent_service.submit.assert_not_called()

    def test_concent_success(self, _put_mock, get_mock, *_):
        self.ttc.concent_enabled = True
        get_mock.return_value = self.ttc
        helpers.send_report_computed_task(
            self.task_server,
            self.wtr,
        )
        self.assert_submit_task_message(self.wtr.subtask_id, self.wtr)

    def test_concent_success_many_files(self, _put_mock, get_mock, *_):
        result = []
        for i in range(100, 300, 99):
            p = pathlib.Path(self.tempdir) / str(i)
            with p.open('wb') as f:
                f.write(b'\0' * i * 2 ** 20)
            result.append(str(p))
        self.wtr.result = result
        self.ttc.concent_enabled = True
        get_mock.return_value = self.ttc
        helpers.send_report_computed_task(
            self.task_server,
            self.wtr,
        )

        self.assert_submit_task_message(self.wtr.subtask_id, self.wtr)

    def test_concent_disabled(self, _put_mock, get_mock, *_):
        self.ttc.concent_enabled = False
        get_mock.return_value = self.ttc
        helpers.send_report_computed_task(
            self.task_server,
            self.wtr,
        )
        self.task_server.client.concent_service.submit.assert_not_called()


@mock.patch(
    'golem.network.history.MessageHistoryService.get_sync_as_message',
)
@mock.patch("golem.network.transport.msg_queue.put")
class TestSendTaskFailure(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.wtf = factories.taskserver.WaitingTaskFailureFactory()
        self.ttc = msg_factories.tasks.TaskToComputeFactory(
            task_id=self.wtf.task_id,
            subtask_id=self.wtf.subtask_id,
            compute_task_def__deadline=int(time.time()) + 3600,
        )

    def test_no_task_to_compute(self, put_mock, get_mock, *_):
        get_mock.return_value = None
        helpers.send_task_failure(self.wtf)
        put_mock.assert_not_called()

    def test_basic(self, put_mock, get_mock, *_):
        get_mock.return_value = self.ttc
        helpers.send_task_failure(self.wtf)
        put_mock.assert_called_once()
