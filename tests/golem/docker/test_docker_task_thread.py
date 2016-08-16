import time
from threading import Thread

from golem.docker.image import DockerImage
from mock import Mock

from golem.docker.task_thread import DockerTaskThread
from test_docker_job import TestDockerJob


class TestDockerTaskThread(TestDockerJob):

    def test_termination(self):
        script = "import time\ntime.sleep(20)"

        task_computer = Mock()
        image = DockerImage("golem/base")
        task_thread = [None]

        def test():
            task_thread[0] = DockerTaskThread(task_computer, "subtask_id", [image],
                                              self.work_dir, script, None, "test task thread",
                                              self.resources_dir, self.output_dir, timeout=25)
            task_thread[0].start()
            time.sleep(1)

        t = Thread(target=test)

        started = time.time()
        t.start()
        time.sleep(1)

        while not task_thread[0].job:
            if time.time() - started > 15:
                self.fail("Job timed out")
                return
            time.sleep(1)

        task_thread[0].join()

        if time.time() - started > 15:
            self.fail("Job timed out")


