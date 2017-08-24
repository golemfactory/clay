import hashlib
import json
import os
import time
from threading import Thread

from mock import Mock, patch

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.docker.image import DockerImage
from golem.docker.task_thread import DockerTaskThread
from golem.task.taskcomputer import TaskComputer
from golem.tools.ci import ci_skip
from .test_docker_job import TestDockerJob


@ci_skip
class TestDockerTaskThread(TestDockerJob):
    def test_termination(self):
        script = "import time\ntime.sleep(20)"

        task_server = Mock()
        task_server.config_desc = ClientConfigDescriptor()
        task_server.config_desc.estimated_blender_performance = 2000.0
        task_server.config_desc.estimated_lux_performance = 2000.0
        task_server.client.datadir = self.test_dir
        task_server.client.get_node_name.return_value = "test_node"
        task_server.get_task_computer_root.return_value = task_server.client.datadir
        task_computer = TaskComputer("node", task_server, use_docker_machine_manager=False)
        image = DockerImage("golemfactory/base", tag="1.2")

        with self.assertRaises(AttributeError):
            DockerTaskThread(task_computer, "subtask_id", None,
                             self.work_dir, script, {}, "test task thread",
                             self.resources_dir, self.output_dir, timeout=30)

        def test():
            tt = DockerTaskThread(task_computer, "subtask_id", [image],
                                  self.work_dir, script, {}, "test task thread",
                                  self.resources_dir, self.output_dir, timeout=30)
            task_computer.current_computations.append(tt)
            task_computer.counting_task = True
            tt.setDaemon(True)
            tt.start()
            time.sleep(1)

        started = time.time()
        parent_thread = Thread(target=test)
        parent_thread.start()
        time.sleep(1)

        ct = task_computer.current_computations[0]

        while ct and ct.is_alive():
            task_computer.run()

            if time.time() - started > 15:
                self.fail("Job timed out")
            elif task_computer.current_computations:
                ct = task_computer.current_computations[0]
            else:
                ct = None

            time.sleep(1)

    def test_receive_message(self):

        HASH = lambda x: hashlib.md5(x.encode()).hexdigest()
        data = {"aa": "bb"}
        data_dump = json.dumps(data)
        data_hash = HASH(data_dump)

        tt = DockerTaskThread(Mock(), "subtask_id", [Mock()],
                              self.work_dir, "", None, "test task thread",
                              self.resources_dir, self.output_dir, timeout=30)

        with patch("logging.Logger.warning") as mock:
            tt.receive_message(data)
            assert mock.called

        tt.job = Mock()
        tt.job.write_work_file = Mock()
        with patch("logging.Logger.warning") as mock:
            tt.receive_message(data)
            args, kwargs = tt.job.write_work_file.call_args
            self.assertEqual(list(args), [
                os.path.join(DockerTaskThread.MESSAGES_IN_DIR, data_hash),
                data_dump])
            self.assertEqual(kwargs, {"options": "w"})
            assert not mock.called

    def test_check_for_new_messages(self):
        HASH = lambda x: hashlib.md5(x.encode()).hexdigest()
        data = {"aa": "bb"}
        data_dumped = json.dumps(data)

        tt = DockerTaskThread(Mock(), "subtask_id", [Mock()],
                              self.work_dir, "", None, "test task thread",
                              self.resources_dir, self.output_dir, timeout=30)

        self.assertEqual(tt.check_for_new_messages(), [{}])

        tt.job = Mock()
        tt.job.read_work_files = Mock(return_value={"a/b.txt": data_dumped})
        tt.job.clean_work_files = Mock()
        msgs = tt.check_for_new_messages()
        self.assertEqual(msgs, [{"filename": "a/b.txt", "content": data}])

        tt.job.read_work_files.assert_called_with(dir=DockerTaskThread.MESSAGES_OUT_DIR)
        tt.job.clean_work_files.assert_called_with(dir=DockerTaskThread.MESSAGES_OUT_DIR)

        data_dumped = "[Not [] valid json"
        tt.job.read_work_files = Mock(return_value={"a/b.txt": data_dumped})

        with patch("logging.Logger.warning") as mock:
            msgs = tt.check_for_new_messages()
            assert mock.called
            self.assertEqual(msgs, [{}])
