import asyncio
import tempfile
from unittest import mock
from pathlib import Path

from golem_messages import factories as msg_factories
from golem_messages.message import tasks as msg_tasks

from twisted.internet import defer

from apps.appsmanager import AppsManager

from golem.resource import resourcemanager
from golem.task import requestedtaskmanager
from golem.task import tasksession
from tests.utils.asyncio import TwistedAsyncioTestCase, AsyncMock


class TestTaskApiReactToWantToComputeTask(TwistedAsyncioTestCase):

    def setUp(self):
        self.ts = tasksession.TaskSession(mock.Mock())
        self.ts.key_id = 'testid'
        self.ts._cannot_assign_task = mock.Mock()
        self.ts.send = mock.Mock()
        self.ts.task_server.get_share_options.return_value.__dict__ = {}

        self.rtm = mock.Mock(spec=requestedtaskmanager.RequestedTaskManager)
        self.rtm.task_exists.return_value = True
        self.rtm.has_pending_subtasks = AsyncMock(return_value=True)
        self.ts.task_server.requested_task_manager = self.rtm

        self.ts.task_server.client.apps_manager = AppsManager()
        self.ts.task_server.client.apps_manager.load_all_apps()

        self.keys_auth = mock.Mock()
        self.keys_auth._private_key = b'4' * 32
        self.keys_auth.public_key = (
            b'@|\xbacR\xea\xeb\x93T\xdcu\xca&9g\x85\xb2z\x85\xcf\xd4\xd5\x85u'
            b'\xdeD\t\x02)-f*4N\x1c\xe8\x18\xb7R \xa4\x9a\xffM\x90\x90p,\xd9'
            b'\x88\x95\xad\xe5 C\x93\x9cZ\xd3\x0f\xbd\xb7\xba\xa0')
        self.ts.task_server.keys_auth = self.keys_auth

        self.resource_manager = mock.Mock(spec=resourcemanager.ResourceManager)
        self.ts.task_server.new_resource_manager = self.resource_manager

        self.wtct = msg_factories.tasks.WantToComputeTaskFactory(
            task_header__environment='BLENDER',
            task_header__sign__privkey=self.keys_auth._private_key,
            price=123,
        )

    @defer.inlineCallbacks
    def test_no_pending_subtasks(self):
        self.rtm.has_pending_subtasks.return_value = False

        yield self.ts._react_to_want_to_compute_task(self.wtct)

        self.rtm.has_pending_subtasks.assert_called_once_with(self.wtct.task_id)
        self.ts._cannot_assign_task.assert_called_once_with(
            self.wtct.task_id,
            msg_tasks.CannotAssignTask.REASON.NoMoreSubtasks,
        )

    @defer.inlineCallbacks
    def test_task_finished(self):
        self.rtm.has_pending_subtasks.return_value = True
        self.rtm.is_task_finished.return_value = True

        yield self.ts._react_to_want_to_compute_task(self.wtct)

        self.rtm.is_task_finished.assert_called_once_with(self.wtct.task_id)
        self.ts._cannot_assign_task.assert_called_once_with(
            self.wtct.task_id,
            msg_tasks.CannotAssignTask.REASON.TaskFinished,
        )

    @defer.inlineCallbacks
    def test_offer_chosen(self):
        random_dir = Path(tempfile.gettempdir())
        self.rtm.get_subtask_inputs_dir.return_value = random_dir
        subtask_def = requestedtaskmanager.SubtaskDefinition(
            subtask_id='test_subtask_id',
            resources=['res1', 'res2'],
            params={'param1': 'value1', 'param2': 'value2'},
            deadline=222,
        )
        subtask_future = asyncio.Future()
        subtask_future.set_result(subtask_def)
        self.rtm.get_next_subtask.return_value = subtask_future
        self.rtm.has_pending_subtasks.return_value = True
        shared_resources = []

        def _share(resource, _):
            return_value = f'hash:{resource}'
            shared_resources.append(return_value)
            return defer.succeed(return_value)
        self.resource_manager.share.side_effect = _share
        tasksession.nodeskeeper.get = mock.Mock(return_value=None)

        yield self.ts._offer_chosen(True, self.wtct)

        self.rtm.get_next_subtask.assert_called_once_with(
            task_id=self.wtct.task_id,
            computing_node=mock.ANY
        )
        for r in subtask_def.resources:
            self.resource_manager.share.assert_any_call(
                random_dir / r,
                mock.ANY)
        self.assertEqual(
            len(subtask_def.resources),
            self.resource_manager.share.call_count,
        )
        self.ts.send.assert_called_once_with(mock.ANY)
        ttc = self.ts.send.call_args[0][0]
        ctd = ttc.compute_task_def
        self.assertEqual(self.wtct.task_id, ctd['task_id'])
        self.assertEqual(subtask_def.subtask_id, ctd['subtask_id'])
        self.assertEqual(subtask_def.deadline, ctd['deadline'])
        self.assertEqual(subtask_def.params, ctd['extra_data'])
        self.assertEqual(shared_resources, ctd['resources'])
