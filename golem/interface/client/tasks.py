import json
from typing import Any, Optional
from uuid import uuid4

from apps.appsmanager import AppsManager
from apps.core.task.coretaskstate import TaskDefinition
from golem.core.deferred import sync_wait
from golem.interface.client.logic import AppLogic
from golem.interface.command import doc, group, command, Argument, CommandResult
from golem.resource.dirmanager import DirManager


class CommandAppLogic(AppLogic):

    def __init__(self, client, datadir):
        super(CommandAppLogic, self).__init__()

        self.node_name = sync_wait(client.get_node_name())
        self.datadir = datadir
        self.dir_manager = DirManager(self.datadir)

    @staticmethod
    def instantiate(client, datadir):
        logic = CommandAppLogic(client, datadir)
        apps_manager = AppsManager()
        apps_manager.load_apps()
        for app in list(apps_manager.apps.values()):
            logic.register_new_task_type(app.task_type_info())
        return logic


@group(help="Manage tasks")
class Tasks:

    client = None  # type: 'golem.rpc.session.Client'

    task_table_headers = ['id', 'remaining', 'subtasks', 'status', 'completion']
    subtask_table_headers = ['node', 'id', 'remaining', 'status', 'completion']
    unsupport_reasons_table_headers = ['reason', 'no of tasks',
                                       'avg for all tasks']

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
                    str(task['time_remaining']),
                    str(task['subtasks']),
                    task['status'],
                    Tasks.__progress_str(task['progress'])
                ])

            return CommandResult.to_tabular(Tasks.task_table_headers, values,
                                            sort=sort)

        if isinstance(result, dict):
            result['progress'] = Tasks.__progress_str(result['progress'])

        return result

    @command(arguments=(id_req, sort_subtask), help="Show sub-tasks")
    def subtasks(self, id, sort):
        values = []

        deferred = Tasks.client.get_subtasks(id)
        result = sync_wait(deferred)

        if isinstance(result, list):
            for subtask in result:
                values.append([
                    subtask['node_name'],
                    subtask['subtask_id'],
                    str(subtask['time_remaining']),
                    subtask['status'],
                    Tasks.__progress_str(subtask['progress'])
                ])

        return CommandResult.to_tabular(Tasks.subtask_table_headers, values,
                                        sort=sort)

    @command(argument=id_req, help="Restart a task")
    def restart(self, id):
        deferred = Tasks.client.restart_task(id)
        return sync_wait(deferred)

    @command(argument=id_req, help="Abort a task")
    def abort(self, id):
        deferred = Tasks.client.abort_task(id)
        return sync_wait(deferred)

    @command(argument=id_req, help="Delete a task")
    def delete(self, id):
        deferred = Tasks.client.delete_task(id)
        return sync_wait(deferred)

    @command(argument=file_name, help="""
        Create a task from file.
        Note: no client-side validation is performed yet.
        This will change in the future
    """)
    def create(self, file_name: str) -> Any:
        with open(file_name) as f:
            self.__create_from_json(f.read())

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

    def __create_from_json(self, jsondata: str) -> Any:
        dictionary = json.loads(jsondata)
        # FIXME CHANGE TASKI ID
        if 'id' in dictionary:
            print("Warning: discarding the UUID from the preset")
        dictionary['id'] = str(uuid4())
        deferred = Tasks.client.create_task(dictionary)
        return sync_wait(deferred)


@group(help="Manage subtasks")
class Subtasks:

    client = None

    subtask_id = Argument('subtask_id', help="Subtask identifier")

    @command(argument=subtask_id, help="Show subtask details")
    def show(self, subtask_id):
        deferred = Subtasks.client.get_subtask(subtask_id)
        return sync_wait(deferred)

    @command(argument=subtask_id, help="Restart a subtask")
    def restart(self, subtask_id):
        deferred = Subtasks.client.restart_subtask(subtask_id)
        return sync_wait(deferred)
