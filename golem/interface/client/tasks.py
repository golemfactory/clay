import cPickle
import collections
import copy
import os
import uuid
from Queue import Queue

from gnr.renderingapplicationlogic import AbsRenderingApplicationLogic
from gnr.renderingtaskstate import RenderingTaskState
from gnr.task.blenderrendertask import build_blender_renderer_info
from gnr.task.luxrendertask import build_lux_render_info
from gnr.task.tasktester import TaskTester
from golem.interface.command import doc, group, command, Argument, CommandHelper, CommandResult
from golem.resource.dirmanager import DirManager
from golem.task.taskbase import Task
from golem.task.taskstate import TaskStatus


def _build_application_logic(client, datadir):
    args = (None, None)

    logic = AbsRenderingApplicationLogic()
    logic.register_new_renderer_type(build_blender_renderer_info(*args))
    logic.register_new_renderer_type(build_lux_render_info(*args))

    logic.datadir = datadir
    logic.node_name = CommandHelper.wait_for(client.get_node_name())

    dir_manager_dict = CommandHelper.wait_for(client.get_dir_manager_dict())
    dir_manager = DirManager.__new__(DirManager)
    dir_manager.__dict__ = dir_manager_dict

    logic.dir_manager = dir_manager

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
        help="File to load a task from"
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

        if isinstance(result, list):
            values = []

            for task in result:
                values.append([
                    task['id'],
                    str(task['time_remaining']),
                    str(task['subtasks']),
                    task['status'],
                    str(int(task['progress'] * 100.0)) + ' %'
                ])

            return CommandResult.to_tabular(Tasks.task_table_headers, values, sort=sort)

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
                    subtask['time_remaining'],
                    subtask['status'],
                    str(int(subtask['progress'] * 100.0)) + ' %'
                ])

        return CommandResult.to_tabular(Tasks.subtask_table_headers, values, sort=sort)

    @command(arguments=(file_name, skip_test), help="Load a task from file")
    def load(self, file_name, skip_test):

        try:
            with open(file_name) as task_file:
                definition = cPickle.loads(task_file.read())
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}".format(file_name, exc))

        definition.resources = {os.path.normpath(res) for res in definition.resources}
        datadir = CommandHelper.wait_for(Tasks.client.get_datadir())

        # TODO: unify GUI and CLI logic

        rendering_task_state = RenderingTaskState()
        rendering_task_state.definition = definition
        rendering_task_state.task_state.status = TaskStatus.starting

        if not Tasks.application_logic:
            Tasks.application_logic = _build_application_logic(Tasks.client, datadir)

        task_builder = Tasks.application_logic.get_builder(rendering_task_state)
        task = Task.build_task(task_builder)
        task.header.task_id = str(uuid.uuid4())

        if not skip_test:

            test_task = copy.deepcopy(task)
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
        return CommandHelper.wait_for(deferred)

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
