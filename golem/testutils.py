import logging
import os
import os.path
import shutil
import tempfile
import unittest
from pathlib import Path
from time import sleep

import ethereum.keys
import pycodestyle

from golem.core.common import get_golem_path, is_windows, is_osx
from golem.core.simpleenv import get_local_datadir
from golem.database import Database
from golem.model import DB_MODELS, db, DB_FIELDS

from golem.resource.dirmanager import DirManager
from golem_messages.factories.datastructures import p2p as dt_p2p_factory
from apps.core.task.coretask import CoreTask, CoreTaskBuilder, CoreTaskTypeInfo
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
import uuid
from golem.docker.job import DockerJob
from golem.docker.client import local_client
import docker.errors
from golem.docker.image import DockerImage
import shutil


logger = logging.getLogger(__name__)


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

    def setUp(self):
        super(TestTaskIntegration, self).setUp()

        # build mock node
        self.node = dt_p2p_factory.Node()
        self.task_definition = None
        self.task = None
        self.dir_manager = DirManager(self.root_dir)

        self.dm = DockerTaskThread.docker_manager = DockerManager.install()


    def build_task(self, task_type_info, task_dict):

        builder_type = task_type_info.task_builder_type

        minimal = False
    
        definition = builder_type.build_definition(task_type_info, task_dict, minimal)
        definition.task_id = str(uuid.uuid4())
        definition.concent_enabled = task_dict.get('concent_enabled', False)

        builder = builder_type(self.node, definition, self.dir_manager)

        self.task_definition = definition
        self.task = builder.build()

        return self.task


    def execute_subtask(self, task):

        node_id = uuid.uuid4()
        node_name = str( node_id )

        ctd = task.query_extra_data(0, node_id, node_name).ctd
        extra_data = ctd[ "extra_data" ]

        subtask_dir = os.path.join(self.root_dir, node_name)
        script_filepath = extra_data['script_filepath']

        self._copy_resources(task, subtask_dir)

        # Run docker job
        env = task.ENVIRONMENT_CLASS
        image = DockerImage(repository=env.DOCKER_IMAGE, tag=env.DOCKER_TAG)

        result = self._create_test_job(image, subtask_dir, script_filepath, extra_data)


    def execute_subtasks(self, num_subtasks):

        for i in range(num_subtasks):
            self.execute_subtask(self.task)


    def _copy_resources(self, task, root_dir):

        [ resources_dir, _, _] = self._create_docker_dirs(root_dir)
        
        for res in task.task_resources:
            shutil.copy(res, resources_dir)


    def _create_docker_dirs(self, root_dir):

        resources_dir = os.path.join(root_dir, "resources")
        work_dir = os.path.join(root_dir, "work")
        output_dir = os.path.join(root_dir, "output")

        os.makedirs(root_dir, exist_ok=True)
        os.makedirs(resources_dir, exist_ok=True)
        os.makedirs(work_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        return [ resources_dir, work_dir, output_dir ]


    def _create_test_job(self, image, root_dir, script, params):

        [ resources_dir, work_dir, output_dir ] = self._create_docker_dirs(root_dir)

        dir_mapping = DockerTaskThread.specify_dir_mapping(
            output=output_dir, temporary=work_dir,
            resources=resources_dir, logs=work_dir, work=work_dir)

        dtt = DockerTaskThread(docker_images=[image],
            extra_data=params,
            dir_mapping=dir_mapping,
            timeout=300)

        dtt.run()
        if dtt.error:
            raise Exception(dtt.error_msg)
        return dtt.result[0] if isinstance(dtt.result, tuple) else dtt.result
