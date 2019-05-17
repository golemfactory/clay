# pylint: disable=no-self-use,redefined-builtin

from datetime import timedelta
import json
import typing
from typing import Any, Optional, Tuple

from apps.core.task.coretaskstate import TaskDefinition
from golem.core.deferred import sync_wait
from golem.interface.command import doc, group, command, Argument, CommandResult
from golem.task.taskstate import TaskStatus

if typing.TYPE_CHECKING:
    from golem.rpc.session import ClientProxy  # noqa pylint: disable=unused-import

CREATE_TASK_TIMEOUT = 300  # s


@group(help="Manage tasks")
class Tasks:

    client: 'ClientProxy'

    task_table_headers = ['id', 'ETA',
                          'subtasks_count', 'status', 'completion']
    subtask_table_headers = ['node', 'id', 'ETA', 'status', 'completion']
    unsupport_reasons_table_headers = ['reason', 'no of tasks',
                                       'avg for all tasks']

    id_req = Argument('id', help="Task identifier")
    id_opt = Argument.extend(id_req, optional=True)
    subtask_ids = Argument('subtask_ids', vargs=True, help="Subtask ids")

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
    force_arg = Argument(
        'force',
        help="Ignore warnings",
        default=False,
        optional=True,
    )
    outfile = Argument(
        'outfile',
        help="Output file",
        optional=True,
    )

    current_task = Argument(
        '--current',
        help='Show only current tasks',
        optional=True,
    )

    last_days = Argument('last_days', optional=True, default="0",
                         help="Number of last days to compute statistics on")

    application_logic = None

    @command(arguments=(id_opt, sort_task, current_task),
             help="Show task details")
    def show(self, id, sort, current):

        deferred = Tasks.client.get_tasks(id)
        result = sync_wait(deferred)

        if not id:
            values = []

            if current:
                result = [t for t in result
                          if TaskStatus(t['status']).is_active()]

            for task in result:
                values.append([
                    task['id'],
                    Tasks.__format_seconds(task['time_remaining']),
                    str(task['subtasks_count']),
                    task['status'],
                    Tasks.__progress_str(task['progress'])
                ])

            return CommandResult.to_tabular(Tasks.task_table_headers, values,
                                            sort=sort)

        if isinstance(result, dict):
            result['time_remaining'] = \
                Tasks.__format_seconds(result['time_remaining'])
            result['progress'] = Tasks.__progress_str(result['progress'])

        return result

    @command(arguments=(id_req, sort_subtask), help="Show sub-tasks")
    def subtasks(self, id, sort):
        values = []

        deferred = Tasks.client.get_subtasks(id)
        result = sync_wait(deferred)

        if result is None:
            return "No subtasks"

        if isinstance(result, list):
            for subtask in result:
                values.append([
                    subtask['node_name'],
                    subtask['subtask_id'],
                    Tasks.__format_seconds(subtask['time_remaining']),
                    subtask['status'],
                    Tasks.__progress_str(subtask['progress'])
                ])

        return CommandResult.to_tabular(Tasks.subtask_table_headers, values,
                                        sort=sort)

    @command(arguments=(id_req, force_arg, ), help="Restart a task")
    def restart(self, id, force: bool = False):
        deferred = Tasks.client._call('comp.task.restart', id, force=force)  # noqa pylint: disable=protected-access
        new_task_id, error = sync_wait(deferred)
        if error:
            return CommandResult(error=error)
        return new_task_id

    @command(arguments=(id_req, subtask_ids, force_arg, ),
             help="Restart given subtasks from a task")
    def restart_subtasks(self, id, subtask_ids, force: bool):
        deferred = Tasks.client._call(  # pylint: disable=protected-access
            'comp.task.restart_subtasks',
            id,
            subtask_ids,
            force=force,
        )
        return sync_wait(deferred)

    @command(argument=id_req, help="Abort a task")
    def abort(self, id):
        deferred = Tasks.client.abort_task(id)
        return sync_wait(deferred)

    @command(argument=id_req, help="Delete a task")
    def delete(self, id):
        deferred = Tasks.client.delete_task(id)
        return sync_wait(deferred)

    @command(help="Deletes all tasks")
    def purge(self):
        deferred = Tasks.client.purge_tasks()
        return sync_wait(deferred)

    @command(arguments=(file_name, force_arg, ), help="""
        Create a task from file.
        Note: no client-side validation is performed yet.
        This will change in the future
    """)
    def create(self, file_name: str, force: bool = False) -> Any:
        with open(file_name) as f:
            task_id, error = self.__create_from_json(f.read(), force=force)
        if error:
            if isinstance(error, dict):
                error = error['error_msg']
            if task_id:
                return CommandResult(error="task {} failed: {}"
                                     .format(task_id, error))
            return CommandResult(error=error)
        return task_id

    @command(arguments=(id_req, outfile), help="Dump an existing task")
    def dump(self, id: str, outfile: Optional[str]) -> None:
        task_dict = sync_wait(self.client.get_task(id))
        self.__dump_dict(task_dict, outfile)

    @command(argument=outfile, help="Dump a task template")
    def template(self, outfile: Optional[str]) -> None:
        template = TaskDefinition()
        self.__dump_dict(template.to_dict(), outfile)

    @doc("Show statistics for tasks")
    def stats(self):
        deferred = Tasks.client.get_task_stats()
        return sync_wait(deferred)

    @command(argument=last_days, help="Show statistics for unsupported tasks")
    def unsupport(self, last_days):
        deferred = Tasks.client.get_unsupport_reasons(int(last_days))
        result = sync_wait(deferred)
        values = [[r['reason'], r['ntasks'], r['avg']] for r in result]
        return CommandResult.to_tabular(Tasks.unsupport_reasons_table_headers,
                                        values)

    @staticmethod
    def __format_seconds(seconds: float) -> str:
        try:
            delta = timedelta(seconds=int(seconds))
            return str(delta)
        except TypeError:
            return '???'

    @staticmethod
    def __dump_dict(dictionary: dict, outfile: Optional[str]) -> None:
        template_str = json.dumps(dictionary, indent=4)
        if outfile:
            with open(outfile, 'w') as dest:
                print(template_str, file=dest)
        else:
            print(template_str)

    @staticmethod
    def __progress_str(progress):
        if progress is None:
            progress = 0
        elif isinstance(progress, str) and progress.endswith('%'):
            return progress
        return '{:.2f} %'.format(progress * 100.0)

    def __create_from_json(self, jsondata: str, **kwargs) \
            -> Tuple[Optional[str], Optional[str]]:
        dictionary = json.loads(jsondata)
        # pylint: disable=protected-access
        deferred = Tasks.client._call('comp.task.create', dictionary, **kwargs)
        return sync_wait(deferred, CREATE_TASK_TIMEOUT)


@group(help="Manage subtasks")
class Subtasks:

    client = None

    subtask_id = Argument('subtask_id', help="Subtask identifier")

    @command(argument=subtask_id, help="Show subtask details")
    def show(self, subtask_id):
        deferred = Subtasks.client.get_subtask(subtask_id)
        result, error = sync_wait(deferred)
        if error:
            return error
        return result

    @command(argument=subtask_id, help="Restart a subtask")
    def restart(self, subtask_id):
        deferred = Subtasks.client.restart_subtask(subtask_id)
        return sync_wait(deferred)
