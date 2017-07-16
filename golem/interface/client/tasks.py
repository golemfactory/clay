import json
from typing import Any, Optional
from uuid import uuid4

from apps.appsmanager import AppsManager
from apps.core.task.coretaskstate import TaskDesc
from apps.core.task.coretaskstate import TaskDefinition

from golem.core.deferred import sync_wait
from golem.core.simpleenv import get_local_datadir
from golem.interface.command import doc, group, command, Argument, CommandResult
from golem.interface.client.logic import AppLogic
from golem.resource.dirmanager import DirManager

# For type annotations:
from golem.client import Client  # pylint: disable=unused-import


class CommandAppLogic(AppLogic):

    def __init__(self, client, datadir):
        super(CommandAppLogic, self).__init__()

        self.node_name = sync_wait(client.get_node_name())
        self.datadir = datadir
        self.dir_manager = DirManager(self.datadir)

    @staticmethod
    def instantiate(client, datadir):
        args = (None, None)
        logic = CommandAppLogic(client, datadir)
        apps_manager = AppsManager()
        apps_manager.load_apps()
        for app in list(apps_manager.apps.values()):
            logic.register_new_task_type(app.task_type_info(*args))
        return logic


@group(help="Manage tasks")
class Tasks:

    client = None  # type: Client

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

    @command(argument=file_name, help="Create a new task file")
    def create(self, file_name):

        # TODO: Add task_type as argument.

        file_path = "{}/{}".format(self.__get_save_dir(), file_name)

        # error if file exists
        # TODO: Unify apps.core.task.coretaskstate._check_output_file()
        try:
            file_exist = os.path.exists(file_path)
            with open(file_path, 'a'):
                pass
            if not file_exist:
                os.remove(file_path)
            else:
                return CommandResult(error="File {} already exists"
                                           .format(file_path))
        except IOError:
            return CommandResult(error="Cannot open output file: {}"
                                       .format(file_path))
        except (OSError, TypeError) as err:
            return CommandResult(error="Output file {} is not properly set: {}"
                                       .format(file_path, err))

        # create new task definition
        task = TaskDesc()

        # save to file
        # TODO: Unify gui.applicationlogic._save_task()
        path = u"{}".format(file_path)
        if not path.endswith(".gt"):
            if not path.endswith("."):
                file_path += "."
            file_path += "gt"
        with open(file_path, "wb") as f:
            data = jsonpickle.dumps(task.definition)
            f.write(data)

        return CommandResult("Task created in file: '{}'."
                             .format(file_path))

    @command(arguments=(file_name, skip_test), help="Load a task from file")
    def load(self, file_name, skip_test):

        try:
            definition = self.__read_from_file(file_name)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}"
                                       .format(file_name, exc))

        if hasattr(definition, 'resources'):
            definition.resources = {os.path.normpath(res)
                                    for res in definition.resources}
        datadir = sync_wait(Tasks.client.get_datadir())

        # TODO: unify GUI and CLI logic

        rendering_task_state = TaskDesc()
        rendering_task_state.definition = definition
        rendering_task_state.task_state.status = TaskStatus.starting

        if not Tasks.application_logic:
            Tasks.application_logic = CommandAppLogic.instantiate(Tasks.client,
                                                                  datadir)

        task_builder = Tasks.application_logic.get_builder(rendering_task_state)
        task = Task.build_task(task_builder)
        rendering_task_state.task_state.outputs = task.get_output_names()
        rendering_task_state.task_state.total_subtasks = task.get_total_tasks()
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
                return CommandResult(error="Test failed: {}"
                                           .format(test_result))

        task_dict = DictSerializer.dump(task)
        task_def = task_dict['task_definition']
        task_def['resources'] = list(task_def.get('task_definition', []))
        deferred = Tasks.client.create_task(task_dict)
        return sync_wait(deferred, timeout=1800)

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

    @command(argument=id_req, help="Pause a task")
    def pause(self, id):
        deferred = Tasks.client.pause_task(id)
        return sync_wait(deferred)

    @command(argument=id_req, help="Resume a task")
    def resume(self, id):
        deferred = Tasks.client.resume_task(id)
        return sync_wait(deferred)

    @command(argument=file_name, help="""
        Create a task from file.
        Note: no client-side validation is performed yet.
        This will change in the future
    """)
    def create(self, file_name: str) -> Any:
        with open(file_name) as f:
            self.create_from_json(f.read())

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

    @staticmethod
    def __dump_dict(dictionary: dict, outfile: Optional[str]) -> None:
        template_str = json.dumps(dictionary, indent=4)
        if outfile:
            with open(outfile, 'w') as dest:
                print(template_str, file=dest)
        else:
            print(template_str)
    

    @staticmethod
    def __get_save_dir():
        save_dir = get_local_datadir("save")
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        return save_dir


    @staticmethod
    def __progress_str(progress):
        if progress is None:
            progress = 0
        elif isinstance(progress, str) and progress.endswith('%'):
            return progress
        return '{:.2f} %'.format(progress * 100.0)

    def create_from_json(self, jsondata: str) -> Any:
        dictionary = json.loads(jsondata)
        # FIXME CHANGE TASKI ID
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
