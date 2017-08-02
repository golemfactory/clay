import os
import shutil
from os import path

from golem.core.common import get_golem_path
from golem.resource.dirmanager import find_task_script
from golem.tools.ci import ci_skip
from .test_docker_job import TestDockerJob


@ci_skip
class TestDummyTaskDockerJob(TestDockerJob):
    """Tests for Docker image golem/base"""

    def _get_test_repository(self):
        return "golemfactory/base"

    def _get_test_tag(self):
        return "1.2"

    def test_dummytask_job(self):
        app_dir = path.join(get_golem_path(), "apps", "dummy")
        task_script = find_task_script(app_dir, "docker_dummytask.py")

        with open(task_script) as f:
            task_script_src = f.read()

        # copy the resources to the resources dir
        dummy_task_dir = path.join(get_golem_path(),
                                 "apps", "lux", "benchmark", "test_task")

        # this is the stuff that is available by "params" module
        # in the docker job script
        params = {
            "data_file": "in.data",
            "subtask_data": "costam",
            "difficulty": 0x00ffffff,
            "result_size": 256,
            "result_file": "out.data",
        }

        with self._create_test_job(script=task_script_src, params=params) as job:
            job.start()
            exit_code = job.wait()
            self.assertEqual(exit_code, 0)

        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ['out42.png'])




