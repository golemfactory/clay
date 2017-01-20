import shutil
import time
from os import makedirs, path

import jsonpickle as json
from mock import Mock

from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder, BlenderRenderTask
from apps.core.task.coretaskstate import AdvanceVerificationOptions
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.docker.image import DockerImage
from golem.node import OptNode
from golem.resource.dirmanager import DirManager
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import result_types, TaskHeader
from golem.task.taskcomputer import DockerTaskThread
from golem.task.taskserver import TaskServer
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture
from golem.tools.appveyor import appveyor_skip
from test_docker_image import DockerTestCase


@appveyor_skip
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
            task_def = json.loads(f.read())

        # Replace $GOLEM_DIR in paths in task definition by get_golem_path()
        golem_dir = get_golem_path()

        def set_root_dir(p):
            return p.replace("$GOLEM_DIR", golem_dir)

        task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        task_def.main_scene_file = set_root_dir(task_def.main_scene_file)
        task_def.main_program_file = set_root_dir(task_def.main_program_file)
        return task_def

    def _create_test_task(self, task_file=CYCLES_TASK_FILE):
        task_def = self._load_test_task_definition(task_file)
        node_name = "0123456789abcdef"
        dir_manager = DirManager(self.path)
        task_builder = BlenderRenderTaskBuilder(node_name, task_def, self.tempdir, dir_manager)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda self_: ()
        return render_task

    def _run_docker_task(self, render_task, timeout=60*5):
        task_id = render_task.header.task_id
        extra_data = render_task.query_extra_data(1.0)
        ctd = extra_data.ctd
        ctd.deadline = timeout_to_deadline(timeout)

        # Create the computing node
        self.node = OptNode(datadir=self.path)
        self.node.client.ranking = Mock()
        self.node.client.start = Mock()
        self.node.client.p2pservice = Mock()
        self.node.initialize()

        ccd = ClientConfigDescriptor()
        ccd.estimated_blender_performance = 2000.0
        ccd.estimated_lux_performance = 2000.0

        task_server = TaskServer(Mock(), ccd, Mock(), self.node.client,
                                 use_docker_machine_manager=False)
        task_computer = task_server.task_computer

        resource_dir = task_computer.resource_manager.get_resource_dir(task_id)
        temp_dir = task_computer.resource_manager.get_temporary_dir(task_id)
        self.dirs_to_remove.append(resource_dir)
        self.dirs_to_remove.append(temp_dir)

        # Copy the task resources
        all_resources = list(render_task.task_resources)
        all_resources.append(render_task.main_program_file)
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
        task_computer.task_given(ctd)
        result = task_computer.resource_given(ctd.task_id)
        self.assertTrue(result)

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
        task_computer = TaskTester(render_task, self.path, Mock(), Mock())
        task_computer.run()
        task_computer.tt.join(60.0)
        return task_computer.tt

    def _run_docker_local_comp_task(self, render_task, timeout=60*5):
        render_task.deadline = timeout_to_deadline(timeout)
        local_computer = LocalComputer(render_task, self.tempdir, Mock(), Mock(),
                                       render_task.query_extra_data_for_test_task)
        local_computer.run()
        local_computer.tt.join(60)
        return local_computer.tt

    def _test_blender_subtask(self, task_file):
        task = self._create_test_task(task_file)
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsNone(error_msg)

        # Check the number and type of result files:
        result = task_thread.result
        self.assertEqual(result["result_type"], result_types["files"])
        self.assertGreaterEqual(len(result["data"]), 3)
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDOUT_FILE for f in result["data"]))
        self.assertTrue(
            any(path.basename(f) == DockerTaskThread.STDERR_FILE for f in result["data"]))
        self.assertTrue(
            any(f.endswith(".png") for f in result["data"]))

    def test_blender_test(self):
        render_task = self._create_test_task()
        tt = self._run_docker_test_task(render_task)
        result, mem = tt.result
        self.assertGreater(mem, 0)

        tt = self._run_docker_local_comp_task(render_task)
        self.assertIsNotNone(tt.result)

    def test_build(self):
        """ Test building docker blender task """
        from golem.network.p2p.node import Node
        node_name = "some_node"
        task_def = self._load_test_task_definition(self.CYCLES_TASK_FILE)
        dir_manager = DirManager(self.path)
        builder = BlenderRenderTaskBuilder(node_name, task_def, self.tempdir, dir_manager)
        task = builder.build()
        self.assertIsInstance(task, BlenderRenderTask)
        self.assertFalse(task.compositing)
        self.assertFalse(task.use_frames)
        self.assertEqual(len(task.frames_given), 10)
        self.assertIsInstance(task.preview_file_path, basestring)
        self.assertIsNone(task.preview_updaters)
        self.assertEqual(task.scale_factor, 0.33)
        self.assertIsNotNone(task.src_code)
        self.assertIsInstance(task.header, TaskHeader)
        self.assertEqual(task.header.task_id, '7220aa01-ad45-4fb4-b199-ba72b37a1f0c')
        self.assertEqual(task.header.task_owner_key_id, '')
        self.assertEqual(task.header.task_owner_address, '')
        self.assertEqual(task.header.task_owner_port, 0)
        self.assertIsInstance(task.header.task_owner, Node)
        self.assertEqual(task.header.subtask_timeout, 1200)
        self.assertEqual(task.header.node_name, 'some_node')
        self.assertGreater(task.header.resource_size, 0)
        self.assertEqual(task.header.environment, 'BLENDER')
        self.assertEqual(task.header.estimated_memory, 0)
        self.assertEqual(task.header.min_version, '0.3')
        self.assertEqual(task.header.docker_images[0].repository, 'golem/blender')
        self.assertEqual(task.header.docker_images[0].tag, 'latest')
        self.assertEqual(task.header.max_price, 10.2)
        self.assertIsNone(task.header.signature)
        self.assertEqual(task.undeletable, [])
        self.assertEqual(task.listeners, [])
        self.assertEqual(len(task.task_resources), 2)
        self.assertTrue(task.task_resources[0].endswith('docker_blendertask.py'))
        self.assertTrue(task.task_resources[1].endswith('scene-Helicopter-27-cycles.blend'))
        self.assertEqual(task.total_tasks, 6)
        self.assertEqual(task.last_task, 0)
        self.assertEqual(task.num_tasks_received, 0)
        self.assertEqual(task.subtasks_given, {})
        self.assertEqual(task.num_failed_subtasks, 0)
        self.assertEqual(task.full_task_timeout, 14400)
        self.assertEqual(task.counting_nodes, {})
        self.assertEqual(task.stdout, {})
        self.assertEqual(task.stderr, {})
        self.assertEqual(task.results, {})
        self.assertEqual(task.res_files, {})
        self.assertTrue(path.isdir(task.tmp_dir))
        self.assertIsInstance(task.verification_options, AdvanceVerificationOptions)
        self.assertEqual(task.verification_options.type, 'forFirst')

    def test_blender_render_subtask(self):
        self._test_blender_subtask(self.BLENDER_TASK_FILE)

    def test_blender_cycles_subtask(self):
        self._test_blender_subtask(self.CYCLES_TASK_FILE)

    def test_blender_subtask_timeout(self):
        task = self._create_test_task()
        task_thread, error_msg, out_dir = \
            self._run_docker_task(task, timeout=1)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(task_thread.error_msg, str)
        self.assertTrue(task_thread.error_msg.startswith("Task timed out"))

    def test_wrong_image_repository_specified(self):
        task = self._create_test_task()
        task.header.docker_images = [DockerImage("%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

    def test_wrong_image_id_specified(self):
        task = self._create_test_task()
        image = task.header.docker_images[0]
        task.header.docker_images = [
            DockerImage(image.repository, image_id="%$#@!!!")]
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        if task_thread:
            self.assertIsNone(task_thread.result)
        self.assertIsInstance(error_msg, str)

    def test_blender_subtask_script_error(self):
        task = self._create_test_task()
        # Replace the main script source with another script that will
        # produce errors when run in the task environment:
        task.src_code = 'main :: IO()\nmain = putStrLn "Hello, Haskell World"\n'
        task.main_program_file = path.join(
            path.join(get_golem_path(), "golem"), "node.py")
        task.task_resources = {task.main_program_file, task.main_scene_file}
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(error_msg, str)
        self.assertTrue(error_msg.startswith("Subtask computation failed"))

    def test_blender_scene_file_error(self):
        task = self._create_test_task()
        # Replace scene file with some other, non-blender file:
        task.main_scene_file = task.main_program_file
        task_thread, error_msg, out_dir = self._run_docker_task(task)
        self.assertIsInstance(task_thread, DockerTaskThread)
        self.assertIsInstance(error_msg, str)
