# pylint: disable=too-few-public-methods,too-many-locals

import json
import os
from os import path
from pathlib import Path
import shutil
from typing import AnyStr, Generic, List, Optional, Type, TypeVar, Union
from unittest.mock import Mock, patch

from apps.core.task.coretask import CoreTask, CoreTaskBuilder
from apps.core.task.coretaskstate import TaskDefinition
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core import variables
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.simpleserializer import DictSerializer
from golem.docker.task_thread import DockerTaskThread
from golem.node import Node
from golem.resource.dirmanager import DirManager
from golem.resource.resourcesmanager import ResourcesManager
from golem.task.taskserver import TaskServer
from golem.testutils import TempDirFixture
from .test_docker_image import DockerTestCase

Task = TypeVar('Task', bound=CoreTask)
Builder = TypeVar('Builder', bound=CoreTaskBuilder, covariant=True)
PathOrStr = Union[Path, AnyStr]


class DockerTaskTestCase(
        TempDirFixture, DockerTestCase, Generic[Task, Builder]):

    TASK_FILE: PathOrStr
    TASK_CLASS: Type[Task]
    TASK_BUILDER_CLASS: Type[Builder]

    def setUp(self) -> None:
        TempDirFixture.setUp(self)
        DockerTestCase.setUp(self)

        self.dirs_to_remove: List[PathOrStr] = []
        self.files_to_remove: List[PathOrStr] = []
        self.node: Optional[Node] = None

    def tearDown(self) -> None:
        if self.node and self.node.client:
            self.node.client.quit()

        for f in self.files_to_remove:
            if os.path.isfile(f):
                os.remove(f)

        for d in self.dirs_to_remove:
            if os.path.isdir(d):
                shutil.rmtree(d)

        DockerTestCase.tearDown(self)
        TempDirFixture.tearDown(self)

    @classmethod
    def _get_test_task_definition(cls) -> TaskDefinition:
        task_path = Path(__file__).parent / cls.TASK_FILE
        with open(task_path) as f:
            json_str = f.read().replace('$GOLEM_DIR', get_golem_path())
            return DictSerializer.load(json.loads(json_str))

    def _get_test_task(self) -> Task:
        self.TASK_CLASS.VERIFICATION_QUEUE._reset()
        task_builder = self.TASK_BUILDER_CLASS(
            node_name="0123456789abcdef",
            task_definition=self._get_test_task_definition(),
            root_path=self.tempdir,
            dir_manager=DirManager(self.tempdir)
        )
        task = task_builder.build()
        task.__class__._update_task_preview = lambda self_: ()
        task.max_pending_client_results = 5
        return task

    def _run_task(self, task: Task, timeout: int = 60 * 5, *_) \
            -> Optional[DockerTaskThread]:
        task_id = task.header.task_id
        extra_data = task.query_extra_data(1.0)
        ctd = extra_data.ctd
        ctd['deadline'] = timeout_to_deadline(timeout)

        # Create the computing node
        self.node = Node(
            datadir=self.path,
            app_config=Mock(),
            config_desc=ClientConfigDescriptor(),
            use_docker_manager=False,
            concent_variant=variables.CONCENT_CHOICES['disabled'],
        )
        with patch('golem.client.EthereumTransactionSystem'):
            self.node.client = self.node._client_factory(Mock())
        self.node.client.start = Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()

        with patch(
            "golem.network.concent.handlers_library.HandlersLibrary"
            ".register_handler"
        ):
            task_server = TaskServer(
                node=Mock(),
                config_desc=ccd,
                client=self.node.client,
                use_docker_manager=False
            )
        patch.object(task_server, 'create_and_set_result_package').start()
        task_server.task_keeper.task_headers[task_id] = task.header
        task_computer = task_server.task_computer

        assert isinstance(task_computer.resource_manager, ResourcesManager)
        resource_dir = Path(
            task_computer.resource_manager.get_resource_dir(task_id))
        temp_dir = Path(
            task_computer.resource_manager.get_temporary_dir(task_id))
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources
        common_prefix = path.commonprefix(list(task.task_resources))
        common_prefix = path.dirname(common_prefix)

        for res_file in task.task_resources:
            dest_file = resource_dir / res_file[len(common_prefix) + 1:]
            dest_dirname = path.dirname(dest_file)
            if not path.exists(dest_dirname):
                os.makedirs(dest_dirname)
            shutil.copyfile(res_file, dest_file)

        # Start task computation
        task_computer.task_given(ctd)
        result = task_computer.resource_given(ctd['task_id'])
        self.assertTrue(result)

        # Thread for task computation should be created by now
        with task_computer.lock:
            task_thread = task_computer.counting_thread

        if task_thread:
            task_thread.join(timeout)
            task_computer.run()

        return task_thread

    @staticmethod
    def _copy_file(old_path: Path, new_path: Path) -> Path:
        if new_path.exists():
            os.remove(new_path)

        if not path.exists(new_path.parent):
            os.makedirs(new_path.parent)

        shutil.copy(old_path, new_path)

        return new_path
