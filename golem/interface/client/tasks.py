import json
import re
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
            return CommandResult(error="Output file {} is not properly set: {}"
                                       .format(file_path, err))

        # create new task definition
        task = TaskDesc()

        # save to file
        self.__save_task_def(file_path, task.definition)

        return CommandResult("Task created in file: '{}'."
                             .format(file_path))

    @command(argument=file_name, help="Test a task from file")
    def test(self, file_name):

        def __error(msg):
            return CommandResult(error="Test failed: {}".format(msg))

        # convert name into full path
        file_path = self.__get_save_path(file_name)

        try:
            definition = self.__read_from_file(file_path)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}"
                                       .format(file_name, exc))

        if hasattr(definition, 'resources'):
            definition.resources = {os.path.normpath(res)
                                    for res in definition.resources}

        datadir = sync_wait(Tasks.client.get_datadir())

        # TODO: allow empty frames inside test?
        # default frames to 1 and keep old_frames for later
        old_frames = definition.options.frames
        if not old_frames:
            definition.options.frames = "1"

        # TODO: unify GUI and CLI logic

        rendering_task_state = TaskDesc()
        rendering_task_state.definition = definition
        task_builder = Tasks.__get_task_builder(rendering_task_state, datadir)

        test_result_raw = Tasks.__test_task(task_builder, datadir)
        test_result = test_result_raw[0]
        # print test_result
        if not test_result:
            return __error(test_result)

        # reset frames to old_frames from the original file
        definition.options.frames = old_frames

        # read stdout file
        stdout_file_path = test_result["data"][0]
        with open(stdout_file_path, 'r') as f:
            stdout = f.read()

        # print stdout

        # parse output data
        prog = "Resolution: (\d+) x (\d+)$.+Frames: (\d+)-(\d+);"
        m = re.search(prog, stdout, re.S | re.M)

        width = int(m.group(1))
        height = int(m.group(2))
        frames_min = int(m.group(3))
        frames_max = int(m.group(4))

        # print "width : {}".format(width)
        # print "height : {}".format(height)
        # print "frames_min : {}".format(frames_min)
        # print "frames_max : {}".format(frames_max)

        # validate result vs definition
        # print jsonpickle.dumps(definition)
        # print definition.resolution

        # validate resolution
        if definition.resolution and len(definition.resolution) > 1:

            if width > definition.resolution[0]:
                return __error("width ({}) > resolution[0] ({})"
                               .format(width, definition.resolution[0]))

            if height > definition.resolution[1]:
                return __error("height ({}) > resolution[1] ({})"
                               .format(height, definition.resolution[1]))
        else:
            # set default resolution
            definition.resolution = [width, height]

        # validate frames & frames_string
        if definition.options.frames_string:
            frames_test = definition.options.frames_string.split("-")
            max_index = len(frames_test) - 1

            if frames_max < int(frames_test[max_index]):
                return __error("frames_max ({}) < last(frames_test) ({})"
                               .format(frames_max, frames_test[max_index]))

            if frames_min > int(frames_test[0]):
                return __error("frames_min ({}) > first(frames_test) ({})"
                               .format(frames_min, frames_test[0]))
        else:
            # set default frame_string
            definition.options.frames_string = "{}-{}".format(frames_min,
                                                              frames_max)

        max_frames = frames_max - frames_min + 1
        if definition.options.frames:
            if max_frames < int(definition.options.frames):
                return __error("max_frames ({}) < options.frames ({})"
                               .format(max_frames, definition.options.frames))
        else:
            # set default frames
            definition.options.frames = "{}".format(max_frames)

        # validate output_format & output_file
        if definition.output_format:
            # TODO: check values
            print("Validate: {}".format(definition.output_format))
        else:
            # set default output_format
            # TODO: find the default for task type.
            definition.output_format = "EXR"

        if definition.output_file:
            # make sure file is writeable
            try:
                if not self.__is_file_writeable(definition.output_file):
                    return __error("File {} already exists"
                                   .format(definition.output_file))
            except IOError:
                return __error("Cannot open output file: {}"
                               .format(definition.output_file))
            except (OSError, TypeError) as err:
                return __error("Output file {} is not properly set: {}"
                               .format(definition.output_file, err))
        else:
            # set default output_file
            msf = os.path.normpath(definition.main_scene_file)
            scene_name = msf[msf.rfind('/')+1:msf.rfind('.')]
            # TODO: find default output_dir
            output_path = "{}{}.{}".format("/tmp/",
                                           scene_name,
                                           definition.output_format)

            definition.output_file = output_path

        # TODO: validate and set defaults:
        #  - subtasks
        #  - compositing
        #  - timeouts

        # print jsonpickle.dumps(definition)

        # testing complete, save task ( TODO: if updated? )
        self.__save_task_def(file_path, definition)

        return CommandResult("Test success: '{}'."
                             .format(test_result))

    @command(arguments=(file_name, skip_test), help="Load a task from file")
    def load(self, file_name, skip_test):

        file_path = Tasks.__get_save_path(file_name)

        try:
            definition = self.__read_from_file(file_path)
        except Exception as exc:
            return CommandResult(error="Error reading task from file '{}': {}"
                                       .format(file_path, exc))

        if hasattr(definition, 'resources'):
            definition.resources = {os.path.normpath(res)
                                    for res in definition.resources}
        datadir = sync_wait(Tasks.client.get_datadir())

        # TODO: unify GUI and CLI logic

        rendering_task_state = TaskDesc()
        rendering_task_state.definition = definition
        rendering_task_state.task_state.status = TaskStatus.starting

        task_builder = Tasks.__get_task_builder(rendering_task_state, datadir)
        task = Task.build_task(task_builder)
        rendering_task_state.task_state.outputs = task.get_output_names()
        rendering_task_state.task_state.total_subtasks = task.get_total_tasks()
        task.header.task_id = str(uuid.uuid4())

        if not skip_test:
            test_result = self.__test_task(task_builder, datadir)
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
    def __get_save_path(file_name):
        name = u"{}".format(file_name)
        if name.startswith("/"):
            file_path = file_name
        else:
            file_path = "{}/{}".format(Tasks.__get_save_dir(), file_name)

        # TODO: Unify gui.applicationlogic._save_task()
        path = u"{}".format(file_path)
        if not path.endswith(".gt"):
            if not path.endswith("."):
                file_path += "."
            file_path += "gt"

        return file_path

    @staticmethod
    def __get_task_builder(task_state, datadir):
        if not Tasks.application_logic:
            Tasks.application_logic = CommandAppLogic.instantiate(Tasks.client,
                                                                  datadir)
        task_builder = Tasks.application_logic.get_builder(task_state)

        return task_builder

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
            return jsonpickle.loads(task_file.read())

    @staticmethod
    def __save_task_def(file_path, task_def):
        # TODO: Unify gui.applicationlogic._save_task()
        with open(file_path, "wb") as f:
            data = jsonpickle.dumps(task_def)
            f.write(data)

    @staticmethod
    def __test_task(task_builder, datadir):

        test_task = Task.build_task(task_builder)
        test_task.header.task_id = str(uuid.uuid4())
        queue = Queue()

        TaskTester(
            test_task, datadir,
            success_callback=lambda *a, **kw: queue.put(a),
            error_callback=lambda *a, **kw: queue.put(a)
        ).run()

        test_result = queue.get()
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
