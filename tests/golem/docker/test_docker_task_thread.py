import time
from threading import Thread

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.docker.image import DockerImage
from golem.task.taskcomputer import TaskComputer
from mock import Mock

from golem.docker.task_thread import DockerTaskThread
from test_docker_job import TestDockerJob


class TestDockerTaskThread(TestDockerJob):

    def test_termination(self):
        script = "import time\ntime.sleep(20)"

        task_server = Mock()
        task_server.config_desc = ClientConfigDescriptor()
        task_server.client.datadir = self.test_dir
        task_server.client.get_node_name.return_value = "test_node"
        task_server.get_task_computer_root.return_value = task_server.client.datadir
        task_computer = TaskComputer("node", task_server, use_docker_machine_manager=False)
        image = DockerImage("golem/base")

        def test():
            tt = DockerTaskThread(task_computer, "subtask_id", [image],
                                  self.work_dir, script, None, "test task thread",
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
