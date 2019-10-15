# pylint: disable=too-many-locals
# pylint: disable=protected-access

import json
import os
from os import path
import time
from pathlib import Path
import shutil
from typing import AnyStr, Generic, List, Optional, Type, TypeVar, Union
from unittest.mock import Mock, patch

from golem_messages.datastructures import p2p as dt_p2p

from apps.core.task.coretask import CoreTask, CoreTaskBuilder
from apps.core.task.coretaskstate import TaskDefinition
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.simpleserializer import DictSerializer
from golem.docker.task_thread import DockerTaskThread
from golem.node import Node
from golem.resource.dirmanager import DirManager
from golem.task.taskcomputer import TaskComputer
from golem.task.taskserver import TaskServer
from golem.testutils import TempDirFixture
from .test_docker_image import DockerTestCase

Task = TypeVar('Task', bound=CoreTask)
Builder = TypeVar('Builder', bound=CoreTaskBuilder, covariant=True)
PathOrStr = Union[Path, AnyStr]


class TaskComputerExt(TaskComputer):

    @property  # type: ignore
    def counting_thread(self):
        return getattr(self, '_counting_thread', None)

    @counting_thread.setter
    def counting_thread(self, value):
        setattr(self, '_counting_thread', value)
        if value:
            setattr(self, 'last_thread', value)


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
            golem_path = get_golem_path()
            json_str = f.read().replace('$GOLEM_DIR',
                                        Path(golem_path).as_posix())
            return DictSerializer.load(json.loads(json_str))

    def _get_test_task(self) -> Task:
        self.TASK_CLASS.VERIFICATION_QUEUE._reset()
        task_builder = self.TASK_BUILDER_CLASS(
            owner=dt_p2p.Node(
                node_name="0123456789abcdef",
                key="0xdeadbeef",
                prv_addr="10.0.0.10",
                prv_port=40102,
                pub_addr="1.2.3.4",
                pub_port=40102,
                p2p_prv_port=40102,
                p2p_pub_port=40102,
                hyperdrive_prv_port=3282,
                hyperdrive_pub_port=3282,
            ),
            task_definition=self._get_test_task_definition(),
            dir_manager=DirManager(self.tempdir)
        )
        task = task_builder.build()
        task.initialize(task_builder.dir_manager)
        task.__class__._update_task_preview = lambda self_: ()
        return task

    def _run_task(
            self,
            task: Task,
            *_,
            timeout: int = 60 * 5,
    ) -> Optional[DockerTaskThread]:
        task_id = task.header.task_id
        node_id = '0xdeadbeef'
        extra_data = task.query_extra_data(1.0, node_id, 'node_name')
        ctd = extra_data.ctd
        ctd['deadline'] = timeout_to_deadline(timeout)

        # Create the computing node
        with patch('golem.node.TransactionSystem'):
            self.node = Node(
                datadir=self.path,
                app_config=Mock(),
                config_desc=ClientConfigDescriptor(),
                use_docker_manager=False,
                concent_variant={'url': None, 'pubkey': None},
            )
        mock_keys_auth = Mock()
        mock_keys_auth.key_id = node_id
        self.node.client = self.node._client_factory(mock_keys_auth)
        self.node.client.start = Mock()
        self.node.client.task_server = Mock()
        self.node.rpc_session = Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()
        ccd.max_memory_size = 1024 * 1024  # 1 GiB
        ccd.num_cores = 1

        with patch("golem.network.concent.handlers_library.HandlersLibrary"
                   ".register_handler"):
            with patch('golem.task.taskserver.TaskComputer', TaskComputerExt):
                task_server = TaskServer(
                    node=Mock(),
                    config_desc=ccd,
                    client=self.node.client,
                    use_docker_manager=False
                )

        patch.object(task_server, '_create_and_set_result_package').start()
        task_server.task_keeper.task_headers[task_id] = task.header
        task_computer = task_server.task_computer

        resource_dir = Path(
            task_computer.dir_manager.get_task_resource_dir(task_id))
        temp_dir = Path(
            task_computer.dir_manager.get_task_temporary_dir(task_id))
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
        task_computer.start_computation()

        task_thread = None
        started = time.time()

        while not task_thread:
            task_thread = getattr(task_computer, 'last_thread', None)
            if time.time() - started > timeout:
                break

        if task_thread:
            task_thread.join(timeout)
            task_computer.check_timeout()

        return task_thread

    @staticmethod
    def _copy_file(old_path: Path, new_path: Path) -> Path:
        if new_path.exists():
            os.remove(new_path)

        if not path.exists(new_path.parent):
            os.makedirs(new_path.parent)

        shutil.copy(old_path, new_path)

        return new_path
