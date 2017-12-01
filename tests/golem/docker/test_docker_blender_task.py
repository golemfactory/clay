import shutil
import time
from os import makedirs, path

import json
import pytest
from mock import Mock

from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder, BlenderRenderTask
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import get_golem_path, timeout_to_deadline
from golem.core.simpleserializer import DictSerializer
from golem.docker.image import DockerImage
from golem.node import OptNode
from golem.resource.dirmanager import DirManager
from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import ResultType, TaskHeader, ComputeTaskDef
from golem.task.taskcomputer import DockerTaskThread
from golem.task.taskserver import TaskServer
from golem.task.tasktester import TaskTester
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from .test_docker_image import DockerTestCase

from golem.core.fileshelper import find_file_with_ext
import os
from os import makedirs, path, remove
from golem.resource.dirmanager import DirManager
from tests.golem.docker.test_docker_luxrender_task import change_file_location


@ci_skip
class TestDockerBlenderTask(TempDirFixture, DockerTestCase):

    CYCLES_TASK_FILE = "docker-blender-cycles-task.json"
    BLENDER_TASK_FILE = "docker-blender-render-task.json"
    BLENDER_TASK_FILE_RUN_PAYLOAD = "docker-blender-render-task-payload.json"
    # GG todo: BLENDER_TASK_FILE_RUN_PAYLOAD shall run with uneven img splitting like:
    # "resolution": [
    #   400,
    #   350
    # ],
    # "total_subtasks": 3

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

        # GG todo
        # def set_root_dir(p, new_root_dir=golem_dir):
        #     return p.replace("$GOLEM_DIR", new_root_dir)
        #
        # task_def.resources = set(set_root_dir(p) for p in task_def.resources)
        # task_def.main_scene_file = set_root_dir(task_def.main_scene_file)
        # task_def.main_program_file = set_root_dir(task_def.main_program_file)
        # task_def.output_file = set_root_dir(task_def.output_file, self.tempdir)

        return task_def

    def _create_test_task(self, task_file=CYCLES_TASK_FILE):
        task_def = self._load_test_task_definition(task_file)
        node_name = "0123456789abcdef"
        dir_manager = DirManager(self.path)
        task_builder = BlenderRenderTaskBuilder(node_name, task_def, self.tempdir, dir_manager)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda self_: ()
        return render_task

    def _extract_results(self, computer, task: BlenderRenderTask, subtask_id):
        """
        Since the local computer use temp dir, you should copy files
        out of there before you use local computer again.
        Otherwise the files would get overwritten
        (during the verification process).
        This is a problem only in test suite.
        In real life provider and requestor are separate machines
        :param computer:
        :param task:
        :return:
        """
        dir_name = os.path.dirname(computer.tt.result['data'][0])
        dane = computer.tt.result['data']

        png = find_file_with_ext(dir_name, [".png"])
        exr = find_file_with_ext(dir_name, [".exr"])

        if task.output_format == "exr":
            path.isfile(exr)
        else:
            assert path.isfile(png)

        # copy to new location
        new_file_dir = path.join(path.dirname(path.dirname(dir_name)),
                                 'extracted_results', subtask_id)
        self.dirs_to_remove.append(new_file_dir) # cleanup after tests

        if task.output_format == "exr":
            new_file = change_file_location(
                exr, path.join(new_file_dir, "newexrfile.exr"))
        else:
            new_file = change_file_location(
                png, path.join(new_file_dir, "newpngfile.png"))

        return new_file

    @pytest.mark.slow
    def test_blender_real_task_png_should_pass(self):
        #arrange
        task = self._create_test_task(self.BLENDER_TASK_FILE_RUN_PAYLOAD)
        ctd = task.query_extra_data(10000).ctd

        #act
        self._test_blender_real_task(task , ctd)

        # assert good results - should pass
        is_subtask_verified = task.verify_subtask(ctd.subtask_id)
        self.assertTrue(is_subtask_verified)
        self.assertEqual(task.num_tasks_received, 1)

    @pytest.mark.slow
    def test_blender_real_task_png_should_fail(self):
        #arrange
        task = self._create_test_task(self.BLENDER_TASK_FILE_RUN_PAYLOAD)
        ctd = task.query_extra_data(10000).ctd

        # act
        computer = LocalComputer(
            task,
            self.tempdir,
            Mock(),
            Mock(),
            lambda: ctd,
        )

        computer.run()
        computer.tt.join()

        file_for_validation = self._extract_results(
            computer, task, ctd.subtask_id)

        task.create_reference_data_for_task_validation()
        self.assertEqual(task.num_tasks_received, 0)

        # assert bad results - should fail
        bad_file = path.join(path.dirname(file_for_validation),
                             "badfile." + task.output_format)

        def make_test_img(img_path, size=(10, 10), color=(255, 0, 0)):
            from PIL import Image
            img = Image.new('RGB', size, color)
            img.save(img_path)
            img.close()

        make_test_img(bad_file, size=(300,200))

        task.computation_finished(ctd.subtask_id,
                                  [bad_file],
                                  result_type=ResultType.FILES)

        is_subtask_verified = task.verify_subtask(ctd.subtask_id)
        self.assertFalse(is_subtask_verified)
        self.assertEqual(task.num_tasks_received, 0)

    def _test_blender_real_task(self, task: BlenderRenderTask,
                                ctd: ComputeTaskDef):
        # act
        computer = LocalComputer(
            task,
            self.tempdir,
            Mock(),
            Mock(),
            lambda: ctd,
        )

        computer.run()
        computer.tt.join()

        file_for_validation = self._extract_results(
            computer, task, ctd.subtask_id)

        task.create_reference_data_for_task_validation()
        self.assertEqual(task.num_tasks_received, 0)
        task.computation_finished(ctd.subtask_id,
                                  [file_for_validation],
                                  result_type=ResultType.FILES)


    def _run_docker_task(self, render_task, timeout=60):
        task_id = render_task.header.task_id
        extra_data = render_task.query_extra_data(1.0)
        ctd = extra_data.ctd
        ctd['deadline'] = timeout_to_deadline(timeout)

        # Create the computing node
        self.node = OptNode(datadir=self.path, use_docker_machine_manager=False)
        self.node.client.ranking = Mock()
        self.node.client.start = Mock()
        self.node.client.p2pservice = Mock()
        self.node._run()

        ccd = ClientConfigDescriptor()

        task_server = TaskServer(Mock(), ccd, Mock(), self.node.client,
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
        task_computer.task_given(ctd)
        result = task_computer.resource_given(ctd['task_id'])
        assert result

        # Thread for task computation should be created by now
        with task_computer.lock:
            task_thread = task_computer.counting_thread

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
        local_computer = LocalComputer(
            render_task, self.tempdir, Mock(), Mock(),
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

    @pytest.mark.slow
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
        assert len(task.frames_given) == 5
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

    @pytest.mark.slow
    def test_blender_render_subtask(self):
        self._test_blender_subtask(self.BLENDER_TASK_FILE)

    @pytest.mark.slow
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
