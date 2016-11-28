import cPickle
import os
import uuid
from Queue import Queue

from apps.blender.task.blenderrendertask import build_blender_renderer_info
from gnr.renderingtaskstate import RenderingTaskState
from gnr.task.luxrendertask import build_lux_render_info
from gnr.task.tasktester import TaskTester
from golem.interface.command import doc, group, command, Argument, CommandHelper, CommandResult
from golem.task.taskbase import Task
from golem.task.taskstate import TaskStatus


class RendererLogic(object):

    def __init__(self, node_name, datadir, dir_manager):
        self.node_name = node_name
        self.datadir = datadir
        self.dir_manager = dir_manager
        self.renderers = {}

    def get_builder(self, task_state):
        renderer = task_state.definition.renderer
        return self.renderers[renderer].task_builder_type(self.node_name, task_state.definition,
                                                          self.datadir, self.dir_manager)

    def register_new_renderer_type(self, renderer):
        self.renderers[renderer.name] = renderer

    @staticmethod
    def instantiate(client, datadir):
        args = (None, None)
        node_name = CommandHelper.wait_for(client.get_node_name())
        dir_manager = CommandHelper.wait_for(client.get_dir_manager())

        logic = RendererLogic(node_name, datadir, dir_manager)
        logic.register_new_renderer_type(build_blender_renderer_info(*args))
        logic.register_new_renderer_type(build_lux_render_info(*args))

        return logic


@group(help="Manage tasks")
class Tasks(object):

    client = None

    task_table_headers = ['id', 'remaining', 'subtasks', 'status', 'completion']
    subtask_table_headers = ['node', 'id', 'remaining', 'status', 'completion']

    id_req = Argument('id', help="Task identifier")
    id_opt = Argument.extend(id_req, optional=True)

    sort_task = Argument(
        '--sort',
        choices=task_table_headers,
        optional=True,
        help="Sort tasks"
    )
    sort_subtask = Argument(
        '--sort',
        choices=subtask_table_headers,
        optional=True,
        help="Sort subtasks"
    )
    file_name = Argument(
        'file_name',
        help="Task file"
    )
    skip_test = Argument(
        '--skip-test',
        default=False,
        help="Skip task testing phase"
    )

    application_logic = None

    @command(arguments=(id_opt, sort_task), help="Show task details")
    def show(self, id, sort):

        deferred = Tasks.client.get_tasks(id)
        result = CommandHelper.wait_for(deferred)

        if not id:
            values = []

            for task in result or []:
                values.append([
                    task['id'],
                    str(task['time_remaining']),
                    str(task['subtasks']),
                    task['status'],
                    Tasks.__progress_str(task['progress'])
                ])

            return CommandResult.to_tabular(Tasks.task_table_headers, values, sort=sort)

        if isinstance(result, dict):
            result['progress'] = Tasks.__progress_str(result['progress'])

        return result

    @command(arguments=(id_req, sort_subtask), help="Show sub-tasks")
    def subtasks(self, id, sort):
        values = []

        deferred = Tasks.client.get_subtasks(id)
        result = CommandHelper.wait_for(deferred)

        if isinstance(result, list):
            for subtask in result:
                values.append([
                    subtask['node_name'],
                    subtask['subtask_id'],
                    str(subtask['time_remaining']),
                    subtask['status'],
                    Tasks.__progress_str(subtask['progress'])
                ])

        return CommandResult.to_tabular(Tasks.subtask_table_headers, values, sort=sort)

    @command(arguments=(file_name, skip_test), help="Load a task from file")
    def load(self, file_name, skip_test):

        try:
            definition = self.__read_from_file(file_name)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}".format(file_name, exc))

        if hasattr(definition, 'resources'):
            definition.resources = {os.path.normpath(res) for res in definition.resources}
        datadir = CommandHelper.wait_for(Tasks.client.get_datadir())

        # TODO: unify GUI and CLI logic

        rendering_task_state = RenderingTaskState()
        rendering_task_state.definition = definition
        rendering_task_state.task_state.status = TaskStatus.starting

        if not Tasks.application_logic:
            Tasks.application_logic = RendererLogic.instantiate(Tasks.client, datadir)

        task_builder = Tasks.application_logic.get_builder(rendering_task_state)
        task = Task.build_task(task_builder)
        task.header.task_id = str(uuid.uuid4())

        if not skip_test:

            test_task = Task.build_task(task_builder)
            test_task.header.task_id = str(uuid.uuid4())
            queue = Queue()

            TaskTester(
                test_task, datadir,
                success_callback=lambda *a, **kw: queue.put(True),
                error_callback=lambda *a, **kw: queue.put(a)
            ).run()

            test_result = queue.get()
            if test_result is not True:
                return CommandResult(error="Test failed: {}".format(test_result))

        deferred = Tasks.client.enqueue_new_task(task)
        return CommandHelper.wait_for(deferred, timeout=1800)

    @command(argument=id_req, help="Restart a task")
    def restart(self, id):
        deferred = Tasks.client.restart_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Abort a task")
    def abort(self, id):
        deferred = Tasks.client.abort_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Delete a task")
    def delete(self, id):
        deferred = Tasks.client.delete_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Pause a task")
    def pause(self, id):
        deferred = Tasks.client.pause_task(id)
        return CommandHelper.wait_for(deferred)

    @command(argument=id_req, help="Resume a task")
    def resume(self, id):
        deferred = Tasks.client.resume_task(id)
        return CommandHelper.wait_for(deferred)

    @doc("Show statistics for tasks")
    def stats(self):
        deferred = Tasks.client.get_task_stats()
        return CommandHelper.wait_for(deferred)

    @staticmethod
    def __progress_str(progress):
        if progress is None:
            progress = 0
        elif isinstance(progress, basestring) and progress.endswith('%'):
            return progress
        return '{:.2f} %'.format(progress * 100.0)

    @staticmethod
    def __read_from_file(file_name):
        with open(file_name) as task_file:
            return cPickle.loads(task_file.read())


@group(help="Manage subtasks")
class Subtasks(object):

    client = None

    subtask_id = Argument('subtask_id', help="Subtask identifier")

    @command(argument=subtask_id, help="Show subtask details")
    def show(self, subtask_id):
        deferred = Subtasks.client.get_subtask(subtask_id)
        return CommandHelper.wait_for(deferred)

    @command(argument=subtask_id, help="Restart a subtask")
    def restart(self, subtask_id):
        deferred = Subtasks.client.restart_subtask(subtask_id)
        return CommandHelper.wait_for(deferred)
