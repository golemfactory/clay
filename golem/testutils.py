import logging
import os
import os.path
import shutil
import string
import tempfile
import unittest
from functools import wraps
from unittest.mock import Mock, patch
from pathlib import Path
from random import SystemRandom
from time import sleep
from typing import Dict


import ethereum.keys
import pycodestyle
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from golem_messages.message import ComputeTaskDef

from apps.appsmanager import AppsManager
from golem.core.common import get_golem_path, is_windows, is_osx
from golem.core.fileshelper import outer_dir_path
from golem.core.keysauth import KeysAuth
from golem.core.simpleenv import get_local_datadir
from golem.database import Database
from golem.docker.image import DockerImage
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.model import DB_MODELS, db, DB_FIELDS
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import TaskEventListener, Task
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager
from golem.clientconfigdescriptor import ClientConfigDescriptor

logger = logging.getLogger(__name__)


class DockerTestJobFailure(Exception):
    pass


class TempDirFixture(unittest.TestCase):
    root_dir = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        logging.basicConfig(level=logging.DEBUG)
        if cls.root_dir is None:
            if is_osx():
                # Use Golem's working directory in ~/Library/Application Support
                # to avoid issues with mounting directories in Docker containers
                cls.root_dir = os.path.join(get_local_datadir('tests'))
                os.makedirs(cls.root_dir, exist_ok=True)
            elif is_windows():
                import win32api  # noqa pylint: disable=import-error
                base_dir = get_local_datadir('default')
                cls.root_dir = os.path.join(base_dir, 'ComputerRes', 'tests')
                os.makedirs(cls.root_dir, exist_ok=True)
                cls.root_dir = win32api.GetLongPathName(cls.root_dir)
            else:
                # Select nice root temp dir exactly once.
                cls.root_dir = tempfile.mkdtemp(prefix='golem-tests-')

    # Concurrent tests will fail
    # @classmethod
    # def tearDownClass(cls):
    #     if os.path.exists(cls.root_dir):
    #         shutil.rmtree(cls.root_dir)

    def setUp(self):

        # KeysAuth uses it. Default val (250k+) slows down the tests terribly
        ethereum.keys.PBKDF2_CONSTANTS['c'] = 1

        prefix = self.id().rsplit('.', 1)[1]  # Use test method name
        self.tempdir = tempfile.mkdtemp(prefix=prefix, dir=self.root_dir)
        self.path = self.tempdir  # Alias for legacy tests
        if not is_windows():
            os.chmod(self.tempdir, 0o770)
        self.new_path = Path(self.path)

    def tearDown(self):
        # Firstly kill Ethereum node to clean up after it later on.
        try:
            self.__remove_files()
        except OSError as e:
            logger.debug("%r", e, exc_info=True)
            tree = ''
            for path, _dirs, files in os.walk(self.path):
                tree += path + '\n'
                for f in files:
                    tree += f + '\n'
            logger.error("Failed to remove files %r", tree)
            # Tie up loose ends.
            import gc
            gc.collect()
            # On windows there's sometimes a problem with syncing all threads.
            # Try again after 3 seconds
            sleep(3)
            self.__remove_files()

    def temp_file_name(self, name: str) -> str:
        return os.path.join(self.tempdir, name)

    def additional_dir_content(self, file_num_list, dir_=None, results=None,
                               sub_dir=None):
        """
        Create recursively additional temporary files in directories in given
        directory.
        For example file_num_list in format [5, [2], [4, []]] will create
        5 files in self.tempdir directory, and 2 subdirectories - first one will
        contain 2 tempfiles, second will contain 4 tempfiles and an empty
        subdirectory.
        :param file_num_list: list containing number of new files that should
            be created in this directory or list describing file_num_list for
            new inner directories
        :param dir_: directory in which files should be created
        :param results: list of created temporary files
        :return:
        """
        if dir_ is None:
            dir_ = self.tempdir
        if sub_dir:
            dir_ = os.path.join(dir_, sub_dir)
            if not os.path.exists(dir_):
                os.makedirs(dir_)
        if results is None:
            results = []
        for el in file_num_list:
            if isinstance(el, int):
                for _ in range(el):
                    t = tempfile.NamedTemporaryFile(dir=dir_, delete=False)
                    results.append(t.name)
            else:
                new_dir = tempfile.mkdtemp(dir=dir_)
                self.additional_dir_content(el, new_dir, results)
        return results

    def __remove_files(self):
        if os.path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)


class DatabaseFixture(TempDirFixture):
    """ Setups temporary database for tests."""

    def setUp(self):
        super(DatabaseFixture, self).setUp()
        self.database = Database(db, fields=DB_FIELDS, models=DB_MODELS,
                                 db_dir=self.tempdir)

    def tearDown(self):
        self.database.db.close()
        super(DatabaseFixture, self).tearDown()


class TestWithClient(TempDirFixture):

    def setUp(self):
        super(TestWithClient, self).setUp()
        self.client = unittest.mock.Mock()
        self.client.datadir = os.path.join(self.path, "datadir")


class PEP8MixIn(object):
    """A mix-in class that adds PEP-8 style conformance.
    To use it in your TestCase just add it to inheritance list like so:
    class MyTestCase(unittest.TestCase, testutils.PEP8MixIn):
        PEP8_FILES = <iterable>

    PEP8_FILES attribute should be an iterable containing paths of python
    source files relative to <golem root>.

    Afterwards your test case will perform conformance test on files mentioned
    in this attribute.
    """

    def test_conformance(self, *_):
        """Test that we conform to PEP-8."""
        style = pycodestyle.StyleGuide(
            ignore=pycodestyle.DEFAULT_IGNORE.split(','),
            max_line_length=80)

        # PyCharm needs absolute paths
        base_path = Path(get_golem_path())
        absolute_files = [str(base_path / path) for path in self.PEP8_FILES]

        result = style.check_files(absolute_files)
        self.assertEqual(result.total_errors, 0,
                         "Found code style errors (and warnings).")


def remove_temporary_dirtree_if_test_passed(fun):
    @wraps(fun)
    def wrapper(self, *args, **kwargs):
        fun(self, *args, **kwargs)
        # If test fails, we won't reach this point, but tearDown
        # will be called and directories won't be removed.
        self.REMOVE_TMP_DIRS = True
    return wrapper


class TestTaskIntegration(DatabaseFixture):

    @staticmethod
    def check_file_existence(filename):
        return os.path.isfile(filename)

    @staticmethod
    def check_dir_existence(dir_path):
        return os.path.isdir(dir_path)

    def setUp(self):
        super(TestTaskIntegration, self).setUp()

        # Assume that test failed. @dont_remove_dirs_on_failed_test decorator
        # will set this variable to True on the end of test.
        self.REMOVE_TMP_DIRS = False

        # build mock node
        self.node = dt_p2p_factory.Node()
        self.task_definition = None
        self.node_id = ''.join(
            SystemRandom().choice(string.ascii_lowercase + string.digits) for _
            in range(8))
        self.node_name = ''.join(
            SystemRandom().choice(string.ascii_lowercase + string.digits) for _
            in range(8))
        self.task = None
        self.dir_manager = DirManager(self.tempdir)

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

    def execute_task(self, task_def):
        task: Task = self._add_task(task_def)
        task_id = task.task_definition.task_id

        logger.info("Executing test task [task_id = {}] "
                    "on mocked provider.".format(task_id))

        self.task_manager.start_task(task_id)
        for i in range(task.task_definition.subtasks_count):
            ctd: ComputeTaskDef = self.task_manager. \
                get_next_subtask(node_id=self.node_id,
                                 task_id=task.task_definition.task_id,
                                 estimated_performance=1000,
                                 price=int(
                                     task.price /
                                     task.task_definition.subtasks_count),
                                 max_resource_size=10000000000,
                                 max_memory_size=10000000000)

            subtask_id = ctd["subtask_id"]

            logger.info("Executing test subtask {}/{} [subtask_id = {}] "
                        "[task_id = {}] on mocked provider.".format(
                            i+1, task.task_definition.subtasks_count,
                            subtask_id, task_id))

            result = self._execute_subtask(task, ctd)
            result = self._collect_results_from_provider(result,
                                                         task_id, subtask_id)

            logger.info("Executing TaskManager.computed_task_received "
                        "[subtask_id = {}] [task_id = {}].".format(subtask_id,
                                                                   task_id))

            self.task_manager.computed_task_received(
                subtask_id=subtask_id,
                result=result,
                verification_finished=None)

            # all results are moved to the parent dir inside
            # computed_task_received
            logger.info("Executing task.accept_results [subtask_id = {}] "
                        "[task_id = {}].".format(subtask_id, task_id))

            task.accept_results(subtask_id, list(
                map(lambda res: outer_dir_path(res), result)))

            # finish subtask
            TaskClient.assert_exists(self.node_id, task.counting_nodes).finish()

        return task

    def _execute_subtask(self, task, ctd):

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
    def _create_docker_dirs(root_dir):

        resources_dir = os.path.join(root_dir, "resources")
        work_dir = os.path.join(root_dir, "work")
        output_dir = os.path.join(root_dir, "output")

        dirs = [resources_dir, work_dir, output_dir]

        for docker_dir in dirs:
            os.makedirs(docker_dir, exist_ok=True)
        return dirs

    def _log_docker_logs(self, dtt):
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

        [resources_dir, work_dir, output_dir] = self._create_docker_dirs(
            root_dir)

        self._copy_resources(task, resources_dir)

        # Run docker job
        env = task.ENVIRONMENT_CLASS
        image = DockerImage(repository=env.DOCKER_IMAGE, tag=env.DOCKER_TAG)

        dir_mapping = DockerTaskThread.specify_dir_mapping(
            output=output_dir, temporary=work_dir,
            resources=resources_dir, logs=work_dir, work=work_dir)

        dtt = DockerTaskThread(docker_images=[image],
                               extra_data=params,
                               dir_mapping=dir_mapping,
                               timeout=task.task_definition.subtask_timeout)

        logger.info("Running docker image {} on mock provider".format(image))

        dtt.run()

        logger.info("Content of docker resources "
                    "directory: {}".format(os.listdir(resources_dir)))
        logger.info("Content of docker work "
                    "directory: {}".format(os.listdir(work_dir)))
        logger.info("Content of docker output "
                    "directory: {}".format(os.listdir(output_dir)))

        self._log_docker_logs(dtt)

        if dtt.error:
            raise DockerTestJobFailure(dtt.error_msg)

        return dtt.result.get('data')

    def tearDown(self):
        if self.REMOVE_TMP_DIRS:
            if os.path.isdir(self.tempdir):
                shutil.rmtree(self.tempdir)
