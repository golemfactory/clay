# pylint: disable=no-self-use,redefined-builtin

from datetime import timedelta
import json
import re
from typing import Any, Optional, Tuple

from apps.core.task.coretaskstate import TaskDefinition
from golem.core.deferred import sync_wait
from golem.interface.command import doc, group, command, Argument, CommandResult

CREATE_TASK_TIMEOUT = 300  # s


@group(help="Manage tasks")
class Tasks:

    client = None  # type: 'golem.rpc.session.Client'

    task_table_headers = ['id', 'ETA',
                          'subtasks', 'status', 'completion']
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
    outfile = Argument(
        'outfile',
        help="Output file",
        optional=True,
    )
    skip_test = Argument(
        '--skip-test',
        default=False,
        help="Skip task testing phase"
    )
    last_days = Argument('last_days', optional=True, default="0",
                         help="Number of last days to compute statistics on")

    application_logic = None

    @command(arguments=(id_opt, sort_task), help="Show task details")
    def show(self, id, sort):

        deferred = Tasks.client.get_tasks(id)
        result = sync_wait(deferred)

        if not id:
            values = []

            for task in result or []:
                values.append([
                    task['id'],
                    Tasks.__format_seconds(task['time_remaining']),
                    str(task['subtasks']),
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

    @command(argument=id_req, help="Restart a task")
    def restart(self, id):
        deferred = Tasks.client.restart_task(id)
        new_task_id, error = sync_wait(deferred)
        if error:
            return CommandResult(error=error)
        return new_task_id

    @command(arguments=(id_req, subtask_ids),
             help="Restart given subtasks from a task")
    def restart_subtasks(self, id, subtask_ids):
        deferred = Tasks.client.restart_subtasks_from_task(id, subtask_ids)
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

    @command(argument=file_name, help="""
        Create a task from file.
        Note: no client-side validation is performed yet.
        This will change in the future
    """)
    def create(self, file_name: str) -> Any:
        with open(file_name) as f:
            task_id, error = self.__create_from_json(f.read())
        if error:
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

    def __create_from_json(self, jsondata: str) \
            -> Tuple[Optional[str], Optional[str]]:
        task_name = ""
        dictionary = json.loads(jsondata)
        if 'name' in dictionary.keys():
            dictionary['name'] = dictionary['name'].strip()
            task_name = dictionary['name']
        if (len(task_name) < 4 or len(task_name) > 24):
            raise ValueError(
                "Length of task name cannot be less "
                "than 4 or more than 24 characters.")
        if not re.match(r"(\w|[\-\. ])+$", task_name):
            raise ValueError(
                "Task name can only contain letters, numbers, "
                "spaces, underline, dash or dot.")
        if 'id' in dictionary:
            print("Warning: discarding the UUID from the preset")

        subtasks = dictionary.get('subtasks', 0)
        options = dictionary.get('options', {})
        optimize_total = bool(options.get('optimize_total', False))
        if subtasks and not optimize_total:
            computed_subtasks = sync_wait(
                Tasks.client.get_subtasks_count(
                    total_subtasks=subtasks,
                    optimize_total=False,
                    use_frames=options.get('frame_count', 1) > 1,
                    frames=[None]*options.get('frame_count', 1),
                ),
                CREATE_TASK_TIMEOUT,
            )
            if computed_subtasks != subtasks:
                raise ValueError(
                    "Subtasks count {:d} is invalid."
                    " Maybe use {:d} instead?".format(
                        subtasks,
                        computed_subtasks,
                    )
                )
        deferred = Tasks.client.create_task(dictionary)
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
