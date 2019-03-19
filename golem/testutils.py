import logging
import os
import os.path
import shutil
import string
import tempfile
import unittest
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
from golem.resource.hyperdrive.resourcesmanager import \
    HyperdriveResourceManager
from golem.task.result.resultmanager import EncryptedResultPackageManager
from golem.task.taskbase import TaskEventListener, Task
from golem.task.taskclient import TaskClient
from golem.task.taskmanager import TaskManager
from golem.task.taskstate import TaskState, TaskStatus

logger = logging.getLogger(__name__)


class TestTaskManager(TaskManager):
    def __init__(
            self, node, keys_auth, root_path,
            tasks_dir="tasks", task_persistence=True,
            apps_manager=AppsManager(), finished_cb=None):
        super(TaskEventListener, self).__init__()

        self.apps_manager = apps_manager
        apps = list(apps_manager.apps.values())
        task_types = [app.task_type_info() for app in apps]
        self.task_types = {t.name.lower(): t for t in task_types}

        self.node = node
        self.keys_auth = keys_auth

        self.tasks: Dict[str, Task] = {}
        self.tasks_states: Dict[str, TaskState] = {}
        self.subtask2task_mapping: Dict[str, str] = {}

        self.task_persistence = task_persistence

        tasks_dir = Path(os.path.join(root_path, tasks_dir))
        self.tasks_dir = tasks_dir / "tmanager"
        if not self.tasks_dir.is_dir():
            self.tasks_dir.mkdir(parents=True)
        self.root_path = root_path
        self.dir_manager = DirManager(self.get_task_manager_root())

        resource_manager = HyperdriveResourceManager(
            self.dir_manager,
            resource_dir_method=self.dir_manager.get_task_temporary_dir,
        )
        self.task_result_manager = EncryptedResultPackageManager(
            resource_manager
        )

        self.activeStatus = [TaskStatus.computing, TaskStatus.starting,
                             TaskStatus.waiting]

        # self.comp_task_keeper = CompTaskKeeper(
        #     tasks_dir,
        #     persist=self.task_persistence,
        # )

        # self.requestor_stats_manager = RequestorTaskStatsManager()
        # self.provider_stats_manager = \
        #     self.comp_task_keeper.provider_stats_manager

        self.finished_cb = finished_cb

        if self.task_persistence:
            self.restore_tasks()


class TempDirFixture(unittest.TestCase):
    root_dir = None

    @classmethod
    def setUpClass(cls):
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
            for path, dirs, files in os.walk(self.path):
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
                for i in range(el):
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

    def test_conformance(self):
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


class TestTaskIntegration(TempDirFixture):
    TEST_FAILED = False

    @staticmethod
    def check_file_existence(filename):
        return lambda: os.path.isfile(filename)

    @staticmethod
    def check_dir_existence(dir_path):
        return lambda: os.path.isdir(dir_path)

    @staticmethod
    def run_asserts(assertions):
        for a in assertions:
            try:
                assert a()
            except AssertionError:
                TestTaskIntegration.TEST_FAILED = True
                raise

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        TestTaskIntegration.TEST_FAILED = False

    def setUp(self):
        super(TestTaskIntegration, self).setUp()

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
        self.dir_manager = DirManager(self.root_dir)

        # load all apps to be enabled for tests
        app_manager = AppsManager()
        app_manager.load_all_apps()

        self.keys_auth = KeysAuth(datadir=self.tempdir,
                                  private_key_name="test_key",
                                  password="test")

        self.task_manager = TestTaskManager(self.node, self.keys_auth,
                                            self.root_dir,
                                            apps_manager=app_manager)

        self.dm = DockerTaskThread.docker_manager = DockerManager.install()

    def _add_task(self, task_dict):

        task = self.task_manager.create_task(task_dict)
        self.task_manager.add_new_task(task)
        return task

    def execute_task(self, task_def):
        task: Task = self._add_task(task_def)

        self.task_manager.start_task(task.task_definition.task_id)
        for i in range(task.task_definition.subtasks_count):
            ctd: ComputeTaskDef = self.task_manager. \
                get_next_subtask(node_id=self.node_id,
                                 node_name=self.node_name,
                                 task_id=task.task_definition.task_id,
                                 estimated_performance=1000,
                                 price=int(
                                     task.price /
                                     task.task_definition.subtasks_count),
                                 max_resource_size=10000000000,
                                 max_memory_size=10000000000,
                                 address='127.0.0.1')
            result = self._execute_subtask(task, ctd)

            self.task_manager.computed_task_received(
                subtask_id=ctd['subtask_id'],
                result=result,
                verification_finished=None)

            # all results are moved to the parent dir
            task.accept_results(ctd['subtask_id'], list(
                map(lambda res: outer_dir_path(res), result)))

            # finish subtask
            TaskClient.assert_exists(self.node_id, task.counting_nodes).finish()

    def _execute_subtask(self, task, ctd):

        extra_data = ctd["extra_data"]

        tempdir = self.task_manager.dir_manager.get_task_temporary_dir(
            task.task_definition.task_id)

        return self._run_test_job(task, tempdir, extra_data)

    @staticmethod
    def _copy_resources(task, resources_dir):

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

        dtt.run()
        if dtt.error:
            raise Exception(dtt.error_msg)
        return dtt.result.get('data')

    @classmethod
    def tearDownClass(cls):
        if not TestTaskIntegration.TEST_FAILED:
            shutil.rmtree(cls.root_dir)
