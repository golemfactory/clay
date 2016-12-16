import json
from Queue import Queue
from contextlib import contextmanager

from golem.rpc.mapping.aliases import Task

from golem.interface.command import doc, group, command, Argument, CommandHelper, CommandResult


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

    @command(argument=file_name, help="Test a task")
    def test(self, file_name):
        try:
            definition = self.__read_from_file(file_name)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}".format(file_name, exc))

        session = Tasks.client._session
        queue = Queue()

        @contextmanager
        def subscribe_context():
            session.register_events([
                (Task.evt_task_check_success, queue.put),
                (Task.evt_task_check_error, queue.put)
            ])
            yield
            session.unregister_events([
                Task.evt_task_check_success,
                Task.evt_task_check_error
            ])

        with subscribe_context():
            Tasks.client.run_test_task(definition)
            result = queue.get(block=True, timeout=300)

        return CommandResult("{}".format(result))

    @command(argument=file_name, help="Start a task")
    def start(self, file_name):
        try:
            definition = self.__read_from_file(file_name)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}".format(file_name, exc))

        deferred = Tasks.client.create_task(definition)
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
            return json.loads(task_file.read())


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
