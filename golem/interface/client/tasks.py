import os
import json
import re
from typing import Any, Optional
from twisted.internet.defer import Deferred
from uuid import uuid4

from apps.appsmanager import AppsManager
from apps.core.task.coretaskstate import TaskDefinition

from golem.core.deferred import sync_wait
from golem.core.simpleenv import get_local_datadir
from golem.interface.command import doc, group, command, Argument, CommandResult
from golem.interface.client.logic import AppLogic
from golem.resource.dirmanager import DirManager
from golem.rpc.mapping.aliases import Task

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

    @command(argument=file_name, help="Test a task from file")
    def test(self, file_name):

        print("Running test for file: {}".format(file_name))

        def __error(msg):
            return CommandResult(error="Test failed: {}".format(msg))

        # convert name into full path
        file_path = self.__get_save_path(file_name)

        try:
            t_dict = self.__read_from_file(file_path)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}"
                                 .format(file_path, exc))

        print(json.dumps(t_dict))
        if hasattr(t_dict, 'resources'):
            t_dict.resources = {os.path.normpath(res)
                                for res in t_dict.resources}

        test_result = self.__test_task(t_dict)
        if not test_result:
            return __error(test_result)
        else:
            after_test_data = test_result["after_test_data"]
            print("test_result: {}".format(after_test_data))
            if "error" in after_test_data["proposed_def"]:
                return __error(after_test_data["proposed_def"]["error"])

        # testing complete, save task ( TODO: if updated? )
        # self.__save_task_def(file_path, result["proposed_def"])

        return CommandResult("Test success: '{}'."
                             .format(test_result))

    @command(arguments=(file_name, skip_test), help="Create a task from file")
    def create(self, file_name, skip_test):

        file_path = Tasks.__get_save_path(file_name)

        try:
            t_dict = self.__read_from_file(file_path)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}"
                                 .format(file_path, exc))

        if hasattr(t_dict, 'resources'):
            t_dict.resources = {os.path.normpath(res)
                                for res in t_dict.resources}

        if not skip_test:
            test_result = self.__test_task(t_dict)
            if test_result is not True:
                return CommandResult(error="Test failed: {}"
                                           .format(test_result))
            elif "error" in test_result["after_test_data"]:
                return CommandResult(error=test_result["after_test_data"]["error"])

        deferred = Tasks.client.create_task(t_dict)
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

    @command(arguments=(id_req, outfile), help="Dump an existing task")
    def dump(self, id: str, outfile: Optional[str]) -> None:
        task_dict = sync_wait(self.client.get_task(id))
        self.__dump_dict(task_dict, outfile)

    @command(argument=file_name, help="Dump a task template")
    def template(self, file_name: Optional[str]) -> Any:
        template = TaskDefinition()
        self.__dump_dict(template.to_dict(), outfile)

    @doc("Show statistics for tasks")
    def stats(self):
        deferred = Tasks.client.get_task_stats()
        return sync_wait(deferred)

    @staticmethod
    def __dump_dict(dictionary: dict, outfile: Optional[str]) -> None:
        template_str = json.dumps(dictionary, indent=4)
        if file_name:
            # transform user input to full path
            file_path = self.__get_save_path(file_name)

            # error if file exists
            try:
                if not self.__is_file_writeable(file_path):
                    return CommandResult(error="File {} already exists"
                                         .format(file_path))
            except IOError:
                return CommandResult(error="Cannot open output file: {}"
                                     .format(file_path))
            except (OSError, TypeError) as err:
                return CommandResult(error="Output file {} not properly set: {}"
                                     .format(file_path, err))

            with open(file_path, 'w') as dest:
                print(template_str, file=dest)

            return CommandResult("Task created in file: '{}'."
                                 .format(file_path))

        return CommandResult(template_str)

    @staticmethod
    def __get_save_dir():
        save_dir = get_local_datadir("save")
        if not os.path.exists(save_dir):
            os.mkdir(save_dir)
        return save_dir

    @staticmethod
    def __get_save_path(file_name):

        # TODO: os independant root check
        if file_name.startswith("/"):
            file_path = file_name
        else:
            file_path = "{}/{}".format(Tasks.__get_save_dir(), file_name)

        # TODO: Unify gui.applicationlogic._save_task()
        if not file_path.endswith(".json"):
            if not file_path.endswith("."):
                file_path += "."
            file_path += "json"

        return file_path

    @staticmethod
    def __is_file_writeable(file_path):
        # TODO: Unify apps.core.task.coretaskstate._check_output_file()
        file_exist = os.path.exists(file_path)
        with open(file_path, 'a'):
            pass
        if not file_exist:
            os.remove(file_path)
        else:
            return False
        return True

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

    @staticmethod
    def __read_from_file(file_name):
        with open(file_name) as task_file:
            return json.loads(task_file.read())

    @staticmethod
    def __save_task_def(file_path, task_def):
        # TODO: Unify gui.applicationlogic._save_task()
        with open(file_path, "wb") as f:
            data = json.dumps(task_def)
            f.write(data)

    def __test_task(self, t_dict):

        deferred = Deferred()

        def on_callback(*args, **kwargs):
            # print("evt_task_test_status {}: {}".format(args, kwargs))
            status = args[0]

            if status == "Error":
                deferred.callback(kwargs)
            elif status == "Success":
                deferred.callback(kwargs)

        # print("subscribing to client events")
        sync_wait(self.client.subscribe(Task.evt_task_test_status, on_callback))

        # print("Starting test task")
        sync_wait(self.client.run_test_task(t_dict))

        print("Waiting for right status")
        test_result = sync_wait(deferred, timeout=20)

        print(test_result)
        # print("Unsubscribe from events")
        sync_wait(self.client.unsubscribe(Task.evt_task_test_status))

        print("Test complete")
        return test_result


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
