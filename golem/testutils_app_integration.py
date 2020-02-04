import logging
import os
import os.path
import shutil
import string
import threading
from random import SystemRandom
from typing import Tuple, List
from unittest.mock import patch
from pathlib import Path

from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from golem_messages.message import ComputeTaskDef

from apps.appsmanager import AppsManager
from apps.core.task.coretask import CoreTask
from apps.core.verification_queue import VerificationQueue
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.keysauth import KeysAuth
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread, DockerDirMapping
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task, TaskResult
from golem.task.taskmanager import TaskManager
from golem.tools.testwithreactor import TestDatabaseWithReactor

logger = logging.getLogger(__name__)


class DockerTestJobFailure(Exception):
    pass


class VerificationWait:

    def __init__(self, task: Task, subtask_id):
        self.task = task
        self.subtask_id = subtask_id
        self.condition_var = threading.Condition(threading.RLock())

        self.is_finished = False

    def wait_until_finished(self, timeout=10) -> bool:
        with self.condition_var:
            while not self.is_finished:
                # If timeout is set to None, we wait for ethernity.
                timed_out = not self.condition_var.wait(timeout=timeout)

                # This implementation can wait much longer then timeout,
                # because we are in loop and timeout is always restarted,
                # but who cares.
                if timed_out and not self.is_finished:
                    return False
        return True

    def on_verification_finished(self):

        task_id = self.task.task_definition.task_id
        logger.info("Verification of [subtask_id = {}] "
                    "[task_id = {}] callback called.".format(self.subtask_id,
                                                             task_id))

        with self.condition_var:
            self.is_finished = True
            self.condition_var.notify_all()


# pylint: disable=too-many-instance-attributes
class TestTaskIntegration(TestDatabaseWithReactor):

    def setUp(self):
        super().setUp()

        # Clean verification queue.
        CoreTask.VERIFICATION_QUEUE = VerificationQueue()

        # build mock node
        self.node = dt_p2p_factory.Node()
        self.node_id = self._generate_node_id()
        self.node_name = self._generate_node_id()
        self.dir_manager = DirManager(self.tempdir)

        logger.info("Tempdir: {}".format(self.tempdir))

        # load all apps to be enabled for tests
        app_manager = AppsManager()
        app_manager.load_all_apps()

        self.keys_auth = KeysAuth(datadir=self.tempdir,
                                  private_key_name="test_key",
                                  password="test")

        ccd = ClientConfigDescriptor()
        tasks_dir = os.path.join(self.tempdir, 'tasks')

        with patch('golem.core.statskeeper.StatsKeeper._get_or_create'):
            self.task_manager = TaskManager(self.node,
                                            self.keys_auth,
                                            self.tempdir,
                                            tasks_dir=tasks_dir,
                                            config_desc=ccd,
                                            apps_manager=app_manager)

        self.dm = DockerTaskThread.docker_manager = DockerManager.install()
        self.verification_timeout = 100

    def execute_task(self, task_def):
        task: Task = self.start_task(task_def)

        for i in range(task.task_definition.subtasks_count):
            result, subtask_id, _ = self.compute_next_subtask(task, i)
            self.assertTrue(self.verify_subtask(task, subtask_id, result))

        return task

    def start_task(self, task_def):
        task: Task = self._add_task(task_def)
        task_id = task.task_definition.task_id

        logger.info("Executing test task [task_id = {}] "
                    "on mocked provider.".format(task_id))

        self.task_manager.start_task(task_id)
        return task

    def compute_next_subtask(self, task: Task, subtask_num: int) -> \
            Tuple[List[str], int, dict]:
        subtask_id, ctd = self.query_next_subtask(task)
        result = self.execute_on_mock_provider(task, ctd, subtask_id,
                                               subtask_num)

        return result, subtask_id, ctd

    def query_next_subtask(self, task: Task):
        ctd: ComputeTaskDef = self.task_manager. \
            get_next_subtask(node_id=self._generate_node_id(),
                             task_id=task.task_definition.task_id,
                             estimated_performance=1000,
                             price=int(
                                 task.price /
                                 task.task_definition.subtasks_count),
                             offer_hash="blaa offeeeeer")

        return ctd["subtask_id"], ctd

    def execute_on_mock_provider(self, task: Task, ctd: dict, subtask_id: int,
                                 subtask_num: int):
        task_id = task.task_definition.task_id

        logger.info("Executing test subtask {}/{} [subtask_id = {}] "
                    "[task_id = {}] on mocked provider."
                    .format(subtask_num + 1,
                            task.task_definition.subtasks_count, subtask_id,
                            task_id))

        result = self._execute_subtask(task, ctd)
        result = self._collect_results_from_provider(result,
                                                     task_id,
                                                     subtask_id)
        return TaskResult(files=result)

    def verify_subtask(self, task: Task, subtask_id, result):
        task_id = task.task_definition.task_id
        verification_lock = VerificationWait(task, subtask_id)

        logger.info("Executing TaskManager.computed_task_received "
                    "[subtask_id = {}] [task_id = {}].".format(subtask_id,
                                                               task_id))

        self.task_manager.computed_task_received(
            subtask_id=subtask_id,
            result=result,
            verification_finished=verification_lock.on_verification_finished)

        timeouted = not verification_lock.wait_until_finished(
            timeout=self.verification_timeout)

        self.assertFalse(timeouted)
        return self.task_manager.verify_subtask(subtask_id)

    def _execute_subtask(self, task: Task, ctd: dict):

        extra_data = ctd["extra_data"]
        provider_tempdir = self._get_provider_dir(ctd["subtask_id"])

        return self._run_test_job(task, provider_tempdir, extra_data)

    @staticmethod
    def _copy_resources(task, resources_dir):

        logger.info("Copy files to docker resources "
                    "directory {}".format(resources_dir))

        for res in task.task_resources:
            shutil.copy(res, resources_dir)

    @staticmethod
    def _create_docker_dirs(root_dir) -> DockerDirMapping:

        resources_dir = os.path.join(root_dir, "resources")

        dir_mapping = DockerDirMapping.generate(
            Path(resources_dir),
            Path(root_dir))

        os.makedirs(dir_mapping.output, exist_ok=True)
        os.makedirs(dir_mapping.work, exist_ok=True)
        os.makedirs(dir_mapping.resources, exist_ok=True)
        os.makedirs(dir_mapping.stats, exist_ok=True)

        return dir_mapping

    @classmethod
    def _log_docker_logs(cls, dtt):
        stdout_file = dtt.dir_mapping.logs / dtt.STDOUT_FILE
        stderr_file = dtt.dir_mapping.logs / dtt.STDERR_FILE

        if os.path.exists(stdout_file) and os.path.isfile(stdout_file):
            with open(stdout_file, "r") as myfile:
                content = myfile.read()
                logger.info("Docker stdout:\n{}".format(content))
        else:
            logger.error("Docker stdout file {} "
                         "doesn't exist.".format(stdout_file))

        if os.path.exists(stderr_file) and os.path.isfile(stderr_file):
            with open(stderr_file, "r") as myfile:
                content = myfile.read()
                logger.info("Docker stderr:\n{}".format(content))
        else:
            logger.error("Docker stderr file {} "
                         "doesn't exist.".format(stderr_file))

    def _run_test_job(self, task, root_dir, params):

        dir_mapping = self._create_docker_dirs(root_dir)

        self._copy_resources(task, dir_mapping.resources)

        # Run docker job
        env = task.ENVIRONMENT_CLASS
        image = DockerImage(repository=env.DOCKER_IMAGE, tag=env.DOCKER_TAG)

        dtt = DockerTaskThread(
            docker_images=[image],
            extra_data=params,
            dir_mapping=dir_mapping,
            timeout=task.task_definition.subtask_timeout)

        logger.info("Running docker image {} on mock provider".format(image))

        dtt.run()

        logger.info("Content of docker resources "
                    "directory: {}".format(os.listdir(dir_mapping.resources)))
        logger.info("Content of docker work "
                    "directory: {}".format(os.listdir(dir_mapping.work)))
        logger.info("Content of docker output "
                    "directory: {}".format(os.listdir(dir_mapping.output)))

        self._log_docker_logs(dtt)

        if dtt.error:
            raise DockerTestJobFailure(dtt.error_msg)

        return dtt.result.get('data')

    def _add_task(self, task_dict):

        task = self.task_manager.create_task(task_dict)
        self.task_manager.add_new_task(task)
        self.task_manager.initialize_task(task)
        return task

    def _get_provider_dir(self, subtask_id):
        return os.path.join(self.tempdir, "mock-provider", subtask_id)

    def _collect_results_from_provider(self, results, task_id, subtask_id):

        logger.info("Collecting results from mock provider {}".format(
            str(results)))

        task_dir = self.dir_manager.get_task_temporary_dir(task_id)
        subtasks_results_dir = os.path.join(task_dir, subtask_id)

        requestor_results = [os.path.join(
            subtasks_results_dir,
            os.path.basename(result)) for result in results]

        for provider_result, requestor_result in zip(results,
                                                     requestor_results):
            os.makedirs(os.path.dirname(requestor_result), exist_ok=True)
            shutil.move(provider_result, requestor_result)

        logger.info("Collected results from mock provider moved to {}".format(
            str(requestor_results)))

        return requestor_results

    @classmethod
    def _generate_node_id(cls):
        return ''.join(
            SystemRandom().choice(string.ascii_lowercase + string.digits) for _
            in range(8))
