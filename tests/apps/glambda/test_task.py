from unittest import TestCase
from uuid import uuid4

from golem_messages.factories.datastructures import p2p
from mock import MagicMock, patch

from apps.glambda.task.glambdatask import GLambdaTask
from apps.glambda.task.glambdatask import (
    GLambdaTaskVerifier,
    GLambdaTaskBuilder,
    GLambdaTaskTypeInfo,
    GLambdaTaskOptions,
    GLambdaBenchmarkTaskBuilder,
    GLambdaBenchmarkTask
)
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.testutils import TempDirFixture
from golem.verificator.verifier import SubtaskVerificationState


def my_test_task(args):
    return 1 + args['b']


test_args = {'b': 2}

TEST_TASK_DEF_DICT = {
    'type': 'GLambda',
    'name': 'my_task',
    'bid': 1,
    'timeout': '00:10:00',
    'subtask_timeout': '00:10:00',
    'subtasks_count': 1,
    'options': {
        'method': GLambdaTask.PythonObjectSerializer.serialize(my_test_task),
        'args': GLambdaTask.PythonObjectSerializer.serialize(test_args),
        'verification': {
            'type': GLambdaTask.VerificationMethod.NO_VERIFICATION},
        'outputs': ['result.json', 'stdout.log', 'stderr.log'],
        'output_path': ''
    }
}


class GLambdaTaskVerifierTestCase(TestCase):
    def test_verifier(self):
        verifier = GLambdaTaskVerifier()
        self.assertTrue(
            verifier._verify_result({'abitrary': 'result accepted'}))


class GLambdaTaskBuilderTestCase(TestCase):
    def test_build_full_definition(self):
        task_def = GLambdaTaskBuilder.build_full_definition(
            GLambdaTaskTypeInfo(), TEST_TASK_DEF_DICT,
        )
        self.assertEqual(task_def.subtasks_count, 1)

        opts: GLambdaTaskOptions = task_def.options
        self.assertEqual(opts.method, TEST_TASK_DEF_DICT['options']['method'])
        self.assertEqual(opts.args, TEST_TASK_DEF_DICT['options']['args'])
        self.assertEqual(opts.verification, {
            'type': GLambdaTask.VerificationMethod.NO_VERIFICATION})
        self.assertEqual(set(opts.outputs),
                         set(['result.json', 'stdout.log', 'stderr.log']))


class GLambdaBenchmarkTaskTestCase(TestCase):
    def test_query_extra_data(self):
        task_def = GLambdaBenchmarkTaskBuilder.build_full_definition(
            GLambdaTaskTypeInfo(), TEST_TASK_DEF_DICT,
        )
        task_def.task_id = str(uuid4())
        dir_manager = DirManager(root_path='/')
        dir_manager.get_task_output_dir = MagicMock()
        dir_manager.get_task_output_dir.return_value = ''

        task = GLambdaBenchmarkTask(
            total_tasks=1, task_definition=task_def,
            root_path='/', owner=p2p.Node(), dir_manager=dir_manager
        )

        data = task.query_extra_data(0.1337, 'test_id', 'test_name')

        self.assertEqual(
            data.ctd['extra_data']['method'],
            TEST_TASK_DEF_DICT['options']['method']
        )

        self.assertEqual(
            data.ctd['extra_data']['args'],
            TEST_TASK_DEF_DICT['options']['args']
        )


class GLambdaTaskTestCase(TempDirFixture):
    def setUp(self):
        super(GLambdaTaskTestCase, self).setUp()
        task_def = GLambdaTaskBuilder.build_full_definition(
            GLambdaTaskTypeInfo(), TEST_TASK_DEF_DICT,
        )
        task_def.task_id = str(uuid4())
        self.task = GLambdaTask(
            total_tasks=1, task_definition=task_def,
            root_path='/', owner=p2p.Node(),
            dir_manager=DirManager(root_path=self.tempdir)
        )

    def test_query_extra_data(self):
        next_subtask_data = {'extra': 'data'}
        with patch(
            'apps.glambda.task.glambdatask.GLambdaTask._get_subtask_data',
            return_value=next_subtask_data,
        ):
            data = self.task.query_extra_data(0.1337, 'test_id', 'test_name')

        self.assertEqual(data.ctd['extra_data'], next_subtask_data)

        self.assertEqual(self.task.subtasks_given[data.ctd['subtask_id']], {
            'subtask_data': {'extra': 'data'},
            'start_task': 1,
            'status': SubtaskStatus.starting,
            'subtask_timeout': 600,
            'subtask_id': data.ctd['subtask_id'],
            'node_id': 'test_id'
        })

    def test_query_extra_data_for_test_task(self):
        next_subtask_data = {'extra': 'data'}
        with patch(
            'apps.glambda.task.glambdatask.GLambdaTask._get_subtask_data',
            return_value=next_subtask_data,
        ):
            data = self.task.query_extra_data(0.1337, 'test_id', 'test_name')
        self.assertEqual(data.ctd['extra_data'], {'extra': 'data'})

    def test_computation_finished_for_arbitrary_result(self):
        """
        Test if VerificatonMethod.NO_VERIFICATION accepts every result
        and sets subtask state to finished.
        """
        results = ['result']
        verif_cb = MagicMock()

        self.task.counting_nodes = MagicMock()
        self.task.should_accept = MagicMock()
        self.task.should_accept.return_value = True
        self.task._copy_results = MagicMock()

        self.task.subtasks_given['some_id'] = {'node_id': 'some_node'}
        self.task.computation_finished('some_id', results, verif_cb)

        self.assertEqual(self.task.num_tasks_received, 1)
        self.assertEqual(self.task.subtasks_given['some_id']['status'],
                         SubtaskStatus.finished)
        verif_cb.assert_called_once()

    def test_external_verification_finish(self):
        self.task.verification_type = \
            GLambdaTask.VerificationMethod.EXTERNALLY_VERIFIED

        results = ['result']
        verif_cb = MagicMock()

        self.task.counting_nodes = MagicMock()
        self.task.should_accept = MagicMock()
        self.task.should_accept.return_value = True
        self.task._copy_results = MagicMock()

        self.task.subtasks_given['some_id'] = {'node_id': 'some_node'}
        self.task.computation_finished('some_id', results, verif_cb)

        self.assertEqual(self.task.subtasks_given['some_id']['verif_cb'],
                         verif_cb)
        self.assertEqual(self.task.results['some_id'],
                         results)
        verif_cb.assert_not_called()

        self.task.external_verify_subtask('some_id',
                                          SubtaskVerificationState.VERIFIED)

        self.assertTrue('verif_cb' not in self.task.subtasks_given['some_id'])
        self.assertEqual(self.task.num_tasks_received, 1)
        verif_cb.assert_called_once()

    def test_external_verification_failed(self):
        self.task.verification_type = \
            GLambdaTask.VerificationMethod.EXTERNALLY_VERIFIED

        results = ['result']
        verif_cb = MagicMock()

        self.task.counting_nodes = MagicMock()
        self.task.should_accept = MagicMock()
        self.task.should_accept.return_value = True
        self.task._copy_results = MagicMock()
        self.task.computation_failed = MagicMock()

        self.task.subtasks_given['some_id'] = {'node_id': 'some_node'}
        self.task.computation_finished('some_id', results, verif_cb)

        self.assertEqual(self.task.subtasks_given['some_id']['verif_cb'],
                         verif_cb)
        self.assertEqual(self.task.results['some_id'],
                         results)
        verif_cb.assert_not_called()

        self.task.external_verify_subtask('some_id',
                                          SubtaskVerificationState.WRONG_ANSWER)

        self.assertTrue('verif_cb' not in self.task.subtasks_given['some_id'])
        self.assertEqual(self.task.num_tasks_received, 0)
        verif_cb.assert_called()
        self.task.computation_failed.assert_called_once()
