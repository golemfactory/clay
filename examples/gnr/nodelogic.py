from examples.gnr.renderingenvironment import BlenderEnvironment
from examples.gnr.task.blenderrendertask import BlenderRenderTaskBuilder
from golem.task.taskbase import Task


class Logic(object):
    def __init__(self, client):
        self.client = client

    def load_environments(self):
        blender_env = BlenderEnvironment()
        blender_env.accept_tasks = True
        self.client.environments_manager.add_environment(blender_env)

    def connect_with_peers(self, peers):
        for peer in peers:
            self.client.connect(peer)

    def add_tasks(self, tasks):
        for task_def in tasks:
            golem_task = Task.build_task(BlenderRenderTaskBuilder(self.client.get_node_name(),
                                                                  task_def,
                                                                  self.client.get_root_path()))
            self.client.enqueue_new_task(golem_task)
