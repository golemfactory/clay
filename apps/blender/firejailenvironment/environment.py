from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder
from apps.blender.firejailenvironment.task_thread import \
    BlenderFirejailTaskThread
from golem.environments.environment import Environment


class FirejailEnvironment(Environment):

    @classmethod
    def get_id(cls):
        return "BLENDER_FIREJAIL"

    def __init__(self) -> None:
        super().__init__()
        self.software.append("firejail")

    # pylint: disable=too-many-arguments
    def get_task_thread(self, taskcomputer, subtask_id, short_desc, src_code,
                        extra_data, task_timeout, working_dir, resource_dir,
                        temp_dir, **kwargs):
        return BlenderFirejailTaskThread(taskcomputer, subtask_id, working_dir,
                                         src_code, extra_data, short_desc,
                                         resource_dir, temp_dir, task_timeout,
                                         **kwargs)

    def get_benchmark(self):
        return BlenderBenchmark(self), BlenderRenderTaskBuilder
