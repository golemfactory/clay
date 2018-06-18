from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.blender.task.blenderrendertask import BlenderRenderTaskBuilder
from apps.blender.firejailenvironment.task_thread import \
    BlenderFirejailTaskThread
from apps.rendering.task.rendering_engine_requirement import \
    RenderingEngineSupport, RenderingEngine
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.environments.environment import Environment


class FirejailEnvironment(Environment):

    @classmethod
    def parse_init_args(cls, **kwargs):
        converted = {}
        if 'rendering_engine' in kwargs:
            engine = RenderingEngine[kwargs['rendering_engine']]
            converted['rendering_engine'] = RenderingEngineSupport(engine)
        return {**kwargs, **converted}

    def get_id(self):
        engine_name = self.rendering_engine_support.engine.name
        return f"BLENDER_{engine_name}"

    def __init__(self, rendering_engine: RenderingEngineSupport, **kwargs)\
            -> None:
        super().__init__(**kwargs)
        self.rendering_engine_support = rendering_engine
        self.software.append("firejail")
        self.memory_limit = None
        self.cpu_num_cores_limit = None

    def change_config(self, config: ClientConfigDescriptor):
        self.memory_limit = config.max_memory_size
        self.cpu_num_cores_limit = config.num_cores

    def get_supports(self):
        return super().get_supports() + [self.rendering_engine_support]

    # pylint: disable=too-many-arguments
    def get_task_thread(self, taskcomputer, subtask_id, short_desc, src_code,
                        extra_data, task_timeout, working_dir, resource_dir,
                        temp_dir, **kwargs):
        rendering_engine = self.rendering_engine_support.engine
        return BlenderFirejailTaskThread(
            taskcomputer, subtask_id, working_dir,
            src_code, extra_data, short_desc,
            resource_dir, temp_dir, task_timeout,
            rendering_engine,
            memory_limit=self.memory_limit,
            cpu_num_cores_limit=self.cpu_num_cores_limit,
            **kwargs)

    def get_benchmark(self):
        return BlenderBenchmark(self), BlenderRenderTaskBuilder
