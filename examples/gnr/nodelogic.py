from examples.gnr.renderingenvironment import BlenderEnvironment, LuxRenderEnvironment
from examples.gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from examples.gnr.task.luxrendertask import LuxRenderTaskBuilder
from golem.task.taskbase import Task


class Logic(object):
    def __init__(self, client):
        self.client = client

    def load_environments(self):
        blender_env = BlenderEnvironment()
        blender_env.accept_tasks = True
        lux_env = LuxRenderEnvironment()
        lux_env.accept_tasks = True
        self.client.environments_manager.add_environment(blender_env)
        self.client.environments_manager.add_environment(lux_env)

    def connect_with_peers(self, peers):
        for peer in peers:
            self.client.connect(peer)

    def add_tasks(self, tasks):
        for task_def in tasks:
            #FIXME: temporary solution
            if task_def.main_scene_file.endswith('.blend'):
                golem_task = Task.build_task(BlenderRenderTaskBuilder(self.client.get_node_name(),
                                                                      task_def,
                                                                      self.client.get_root_path()))
            else:
                golem_task = Task.build_task(LuxRenderTaskBuilder(self.client.get_node_name(),
                                                                  task_def,
                                                                  self.client.get_root_path()))

            self.client.enqueue_new_task(golem_task)
