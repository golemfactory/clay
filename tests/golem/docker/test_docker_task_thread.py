import time
from threading import Thread
from unittest import TestCase
from unittest.mock import Mock

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.docker.image import DockerImage
from golem.docker.task_thread import DockerTaskThread, EXIT_CODE_MESSAGE
from golem.envs.docker.cpu import DockerCPUEnvironment
from golem.task.taskcomputer import TaskComputer
from golem.tools.ci import ci_skip
from golem.tools.testwithdatabase import TestWithDatabase
from .test_docker_job import TestDockerJob


@ci_skip
class TestDockerTaskThread(TestDockerJob, TestWithDatabase):
    def setUp(self):
        TestWithDatabase.setUp(self)
        TestDockerJob.setUp(self)

    def tearDown(self):
        TestDockerJob.tearDown(self)
        TestWithDatabase.tearDown(self)

    def test_termination(self):
        task_server = Mock()
        task_server.config_desc = ClientConfigDescriptor()
        task_server.config_desc.max_memory_size = 1024 * 1024  # 1 GiB
        task_server.config_desc.num_cores = 1
        task_server.client.datadir = self.test_dir
        task_server.benchmark_manager = Mock()
        task_server.benchmark_manager.benchmarks_needed.return_value = False
        task_server.client.get_node_name.return_value = "test_node"
        task_server.get_task_computer_root.return_value = \
            task_server.client.datadir
        docker_cpu_env = Mock(spec=DockerCPUEnvironment)
        task_computer = TaskComputer(
            task_server,
            docker_cpu_env,
            use_docker_manager=False)
        image = DockerImage("golemfactory/base", tag="1.4")

        with self.assertRaises(AttributeError):
            dir_mapping = DockerTaskThread.generate_dir_mapping(
                self.resources_dir, self.output_dir)
            DockerTaskThread(None, None,
                             dir_mapping, timeout=30)

        def test():
            dir_mapping = DockerTaskThread.generate_dir_mapping(
                self.resources_dir, self.output_dir)
            tt = DockerTaskThread([image], None, dir_mapping, timeout=30)
            task_computer.counting_thread = tt
            task_computer.counting_task = True
            tt.setDaemon(True)
            tt.start()
            time.sleep(1)

        started = time.time()
        parent_thread = Thread(target=test)
        parent_thread.start()
        time.sleep(1)

        ct = task_computer.counting_thread

        while ct and ct.is_alive():
            task_computer.check_timeout()

            if time.time() - started > 15:
                self.fail("Job timed out")
            else:
                ct = task_computer.counting_thread

            time.sleep(1)


class TestExitCodeMessage(TestCase):

    def test_exit_code_message(self):
        exit_code = 1
        message = DockerTaskThread._exit_code_message(exit_code)
        assert message == EXIT_CODE_MESSAGE.format(exit_code)

        exit_code = 137
        message = DockerTaskThread._exit_code_message(exit_code)
        assert message != EXIT_CODE_MESSAGE.format(exit_code)
        assert "out-of-memory" in message

        exit_code = 111
        message = DockerTaskThread._exit_code_message(exit_code)
        assert message != EXIT_CODE_MESSAGE.format(exit_code)
        assert "CPU budget exceeded" in message
