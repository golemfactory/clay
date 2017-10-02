import json
from os import makedirs, path
import shutil
import time
import unittest.mock as mock

from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder, BlenderRenderTask
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.simpleserializer import DictSerializer
from golem.docker.image import DockerImage
from golem.network.p2p.node import Node
from golem.node import OptNode
from golem.resource.dirmanager import DirManager
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ResultType, TaskHeader
from golem.task.taskcomputer import DockerTaskThread
from golem.task.taskserver import TaskServer
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from .test_docker_image import DockerTestCase


@ci_skip
class TestDockerBlenderTask(TempDirFixture, DockerTestCase):

    CYCLES_TASK_FILE = "docker-blender-cycles-task.json"
    BLENDER_TASK_FILE = "docker-blender-render-task.json"

    def setUp(self):
        TempDirFixture.setUp(self)
        DockerTestCase.setUp(self)

        self.error_msg = None
        self.dirs_to_remove = []
        self.node = None

        self._send_task_failed = TaskServer.send_task_failed

    def tearDown(self):
        if self.node and self.node.client:
            self.node.client.quit()
        for dir in self.dirs_to_remove:
            shutil.rmtree(dir)

        TaskServer.send_task_failed = self._send_task_failed

        DockerTestCase.tearDown(self)
        TempDirFixture.tearDown(self)

    def _load_test_task_definition(self, task_file):
        task_file = path.join(path.dirname(__file__), task_file)
        with open(task_file, "r") as f:
            task_def = DictSerializer.load(json.loads(f.read()))

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        golem_dir = get_golem_path()

        def set_root_dir(p):
            return p.replace("$GOLEM_DIR", golem_dir)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_scene_file = set_root_dir(task_def.main_scene_file)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        return task_def

    @staticmethod
    def _create_task_owner():
        return Node(
            node_name='requestor',
            key='1' * 32,
            prv_addr='10.0.0.2',
            prv_port=10000,
            pub_addr='1.2.3.4',
            pub_port=10000,
            nat_type=None,
            prv_addresses=None
        )

    def _create_test_task(self, task_file=CYCLES_TASK_FILE):
        task_def = self._load_test_task_definition(task_file)
        node_name = "0123456789abcdef"
        dir_manager = DirManager(self.path)
        task_builder = BlenderRenderTaskBuilder(node_name, task_def, self.tempdir, dir_manager)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda self_: ()
        render_task.header.task_owner = self._create_task_owner()

        owner = render_task.header.task_owner
        owner.task_owner_key_id = owner.key
        owner.task_owner_address = owner.pub_addr
        owner.task_owner_port = owner.pub_port

        return render_task

    def _run_docker_task(self, render_task, timeout=60*5):
        task_id = render_task.header.task_id
        extra_data = render_task.query_extra_data(1.0)

        ctd = extra_data.ctd
        # missing fields (provided by TaskManager)
        ctd.deadline = timeout_to_deadline(timeout)
        ctd.key_id = render_task.header.task_owner_key_id
        ctd.return_address = render_task.header.task_owner_address
        ctd.return_port = render_task.header.task_owner_port
        ctd.task_owner = render_task.header.task_owner

        # Create the computing node
        self.node = OptNode(datadir=self.path, use_docker_machine_manager=False)
        self.node.client.ranking = mock.Mock()
        self.node.client.start = mock.Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()
        ccd.estimated_blender_performance = 2000.0
        ccd.estimated_lux_performance = 2000.0

        task_server = TaskServer(mock.Mock(), ccd, mock.Mock(), self.node.client, mock.Mock(),
                                 use_docker_machine_manager=False)
        task_server.task_keeper.task_headers[task_id] = render_task.header
        task_computer = task_server.task_computer

        resource_dir = task_computer.resource_manager.get_resource_dir(task_id)
        temp_dir = task_computer.resource_manager.get_temporary_dir(task_id)
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources
        all_resources = list(render_task.task_resources)
        common_prefix = path.commonprefix(all_resources)
        common_prefix = path.dirname(common_prefix)

        for res_file in all_resources:
            dest_file = path.join(resource_dir,
                                  path.relpath(res_file, common_prefix))
            dest_dirname = path.dirname(dest_file)
            if not path.exists(dest_dirname):
                makedirs(dest_dirname)
            shutil.copyfile(res_file, dest_file)

        def send_task_failed(self_, subtask_id, task_id, error_msg, *args):
            self.error_msg = error_msg

        TaskServer.send_task_failed = send_task_failed

        # Start task computation
        assert task_computer.task_given(ctd)
        assert task_computer.resource_given(ctd.task_id)

        # Thread for task computation should be created by now
        task_thread = None
        with task_computer.lock:
            if task_computer.current_computations:
                task_thread = task_computer.current_computations[0]

        if task_thread:
            started = time.time()
            while task_thread.is_alive():
                if time.time() - started >= 60:
                    task_thread.end_comp()
                    break
                time.sleep(1)
                task_computer.run()

        started = time.time()
        while task_computer.counting_task:
            if time.time() - started >= 5:
                raise Exception("Computation timed out")
            time.sleep(0.1)

        return task_thread, self.error_msg, temp_dir

    def _run_docker_test_task(self, render_task, timeout=60*5):
        render_task.deadline = timeout_to_deadline(timeout)
        task_computer = TaskTester(render_task, self.path, mock.Mock(), mock.Mock())
        task_computer.run()
        task_computer.tt.join(60.0)
        return task_computer.tt

    def _run_docker_local_comp_task(self, render_task, timeout=60*5):
        render_task.deadline = timeout_to_deadline(timeout)
        local_computer = LocalComputer(
            render_task, self.tempdir, mock.Mock(), mock.Mock(),
            render_task.query_extra_data_for_test_task)
        local_computer.run()
        local_computer.tt.join(60)
        return local_computer.tt

    def _test_blender_subtask(self, task_file):
        task = self._create_test_task(task_file)
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        assert isinstance(task_thread, DockerTaskThread)
        assert not error_msg

        # Check the number and type of result files:
        result = task_thread.result
        assert result["result_type"] == ResultType.FILES
        assert len(result["data"]) >= 3
        assert any(path.basename(f) == DockerTaskThread.STDOUT_FILE
                   for f in result["data"])
        assert any(path.basename(f) == DockerTaskThread.STDERR_FILE
                   for f in result["data"])
        assert any(f.endswith(".png") for f in result["data"])

    def test_blender_test(self):
        render_task = self._create_test_task()
        tt = self._run_docker_test_task(render_task)
        result, mem = tt.result
        assert mem > 0

        tt = self._run_docker_local_comp_task(render_task)
        assert tt.result

    def test_build(self):
        """ Test building docker blender task """
        from golem.network.p2p.node import Node
        node_name = "some_node"
        task_def = self._load_test_task_definition(self.CYCLES_TASK_FILE)
        dir_manager = DirManager(self.path)
        builder = BlenderRenderTaskBuilder(node_name, task_def, self.tempdir,
                                           dir_manager)
        task = builder.build()
        assert isinstance(task, BlenderRenderTask)
        assert not task.compositing
        assert not task.use_frames
        assert len(task.frames_given) == 10
        assert isinstance(task.preview_file_path, str)
        assert not task.preview_updaters
        assert task.scale_factor == 0.8
        assert task.src_code
        assert isinstance(task.header, TaskHeader)
        assert task.header.task_id == '7220aa01-ad45-4fb4-b199-ba72b37a1f0c'
        assert task.header.task_owner_key_id == ''
        assert task.header.task_owner_address == ''
        assert task.header.task_owner_port == 0
        assert isinstance(task.header.task_owner, Node)
        assert task.header.subtask_timeout == 1200
        assert task.header.node_name == 'some_node'
        assert task.header.resource_size > 0
        assert task.header.environment == 'BLENDER'
        assert task.header.estimated_memory == 0
        assert task.header.docker_images[0].repository == 'golemfactory/blender'
        assert task.header.docker_images[0].tag == '1.3'
        assert task.header.max_price == 10.2
        assert not task.header.signature
        assert task.listeners == []
        assert len(task.task_resources) == 1
        assert task.task_resources[0].endswith(
            'scene-Helicopter-27-cycles.blend')
        assert task.total_tasks == 6
        assert task.last_task == 0
        assert task.num_tasks_received == 0
        assert task.subtasks_given == {}
        assert task.num_failed_subtasks == 0
        assert task.full_task_timeout == 14400
        assert task.counting_nodes == {}
        assert task.stdout == {}
        assert task.stderr == {}
        assert task.results == {}
        assert task.res_files == {}
        assert path.isdir(task.tmp_dir)
        assert task.verificator.verification_options is None

    def test_blender_render_subtask(self):
        self._test_blender_subtask(self.BLENDER_TASK_FILE)

    def test_blender_cycles_subtask(self):
        self._test_blender_subtask(self.CYCLES_TASK_FILE)

    def test_blender_subtask_timeout(self):
        task = self._create_test_task()
        task_thread, error_msg, out_dir = \
            self._run_docker_task(task, timeout=1)
        assert isinstance(task_thread, DockerTaskThread)
        assert isinstance(task_thread.error_msg, str)
        assert task_thread.error_msg.startswith("Task timed out")

    def test_wrong_image_repository_specified(self):
        task = self._create_test_task()
        task.header.docker_images = [DockerImage("%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        if task_thread:
            assert not task_thread.result
        assert isinstance(error_msg, str)

    def test_wrong_image_id_specified(self):
        task = self._create_test_task()
        image = task.header.docker_images[0]
        task.header.docker_images = [
            DockerImage(image.repository, image_id="%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        if task_thread:
            assert not task_thread.result
        assert isinstance(error_msg, str)

    def test_blender_subtask_script_error(self):
        task = self._create_test_task()
        # Replace the main script source with another script that will
        # produce errors when run in the task environment:
        task.src_code = 'main :: IO()\nmain = putStrLn "Hello, Haskell World"\n'
        task.main_program_file = path.join(
            path.join(get_golem_path(), "golem"), "node.py")
        task.task_resources = {task.main_program_file, task.main_scene_file}
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        assert isinstance(task_thread, DockerTaskThread)
        assert isinstance(error_msg, str)
        assert error_msg.startswith("Subtask computation failed")

    def test_blender_scene_file_error(self):
        task = self._create_test_task()
        # Replace scene file with some other, non-blender file:
        task.main_scene_file = task.main_program_file
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        assert isinstance(task_thread, DockerTaskThread)
        assert isinstance(error_msg, str)
