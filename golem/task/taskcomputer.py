import sys
import time
import os
import logging
import requests

sys.path.append('../manager')

from threading import Thread, Lock

from copy import copy

from golem.vm.vm import PythonProcVM, PythonTestVM
from golem.manager.nodestatesnapshot import TaskChunkStateSnapshot
from golem.resource.resourcesmanager import ResourcesManager
from golem.resource.dirmanager import DirManager
from golem.task.docker.job import DockerJob

logger = logging.getLogger(__name__)


class TaskComputer(object):
    """ TaskComputer is responsible for task computations that take place in Golem application. Tasks are started
    in separate threads.
    """
    def __init__(self, node_name, task_server):
        """ Create new task computer instance
        :param node_name:
        :param task_server:
        :return:
        """
        self.node_name = node_name
        self.task_server = task_server
        self.waiting_for_task = None
        self.counting_task = False
        self.current_computations = []
        self.lock = Lock()
        self.last_task_request = time.time()
        self.task_request_frequency = task_server.config_desc.task_request_interval
        self.use_waiting_ttl = task_server.config_desc.use_waiting_for_task_timeout
        self.waiting_for_task_timeout = task_server.config_desc.waiting_for_task_timeout
        self.waiting_ttl = 0
        self.last_checking = time.time()
        self.dir_manager = DirManager(task_server.get_task_computer_root(), self.node_name)

        self.resource_manager = ResourcesManager(self.dir_manager, self)

        self.assigned_subtasks = {}
        self.task_to_subtask_mapping = {}
        self.max_assigned_tasks = 1

        self.delta = None
        self.task_timeout = None
        self.last_task_timeout_checking = None

    def task_given(self, ctd, subtask_timeout):
        if ctd.subtask_id not in self.assigned_subtasks:
            self.assigned_subtasks[ctd.subtask_id] = ctd
            self.assigned_subtasks[ctd.subtask_id].timeout = subtask_timeout
            self.task_to_subtask_mapping[ctd.task_id] = ctd.subtask_id
            self.__request_resource(ctd.task_id, self.resource_manager.get_resource_header(ctd.task_id), ctd.return_address,
                                    ctd.return_port, ctd.key_id, ctd.task_owner)
            return True
        else:
            return False

    def resource_given(self, task_id):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.waiting_ttl = 0
                self.counting_task = True
                subtask = self.assigned_subtasks[subtask_id]
                self.__compute_task(subtask_id, subtask.docker_images,
                                    subtask.src_code, subtask.extra_data,
                                    subtask.short_description, subtask.timeout)
                self.waiting_for_task = None
                return True
            else:
                return False

    def task_resource_collected(self, task_id):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.waiting_ttl = 0
                self.counting_task = True
                subtask = self.assigned_subtasks[subtask_id]
                self.task_timeout = subtask.timeout
                self.last_task_timeout_checking = time.time()
                self.task_server.unpack_delta(self.dir_manager.get_task_resource_dir(task_id), self.delta, task_id)
                self.__compute_task(subtask_id, subtask.docker_images,
                                    subtask.src_code, subtask.extra_data,
                                    subtask.short_description, subtask.timeout)
                self.waiting_for_task = None
                self.delta = None
                return True
            else:
                return False

    def wait_for_resources(self, task_id, delta):
        if task_id in self.task_to_subtask_mapping:
            subtask_id = self.task_to_subtask_mapping[task_id]
            if subtask_id in self.assigned_subtasks:
                self.delta = delta

    def task_request_rejected(self, task_id, reason):
        self.waiting_for_task = None
        logger.warning("Task {} request rejected: {}".format(task_id, reason))

    def resource_request_rejected(self, subtask_id, reason):
        self.waiting_for_task = None
        self.waiting_ttl = 0
        logger.warning("Task {} resource request rejected: {}".format(subtask_id, reason))
        del self.assigned_subtasks[subtask_id]

    def task_computed(self, task_thread):
        with self.lock:
            self.counting_task = False
            if task_thread in self.current_computations:
                self.current_computations.remove(task_thread)

            subtask_id = task_thread.subtask_id

            subtask = self.assigned_subtasks.get(subtask_id)
            if subtask:
                del self.assigned_subtasks[subtask_id]
            else:
                logger.error("No subtask with id {}".format(subtask_id))
                return

            if task_thread.error:
                self.task_server.send_task_failed(subtask_id, subtask.task_id, task_thread.error_msg,
                                                  subtask.return_address, subtask.return_port, subtask.key_id,
                                                  subtask.task_owner, self.node_name)
            elif task_thread.result and 'data' in task_thread.result and 'result_type' in task_thread.result:
                logger.info("Task {} computed".format(subtask_id))
                self.task_server.send_results(subtask_id, subtask.task_id, task_thread.result, subtask.return_address,
                                              subtask.return_port, subtask.key_id, subtask.task_owner, self.node_name)
            else:
                self.task_server.send_task_failed(subtask_id, subtask.task_id, "Wrong result format",
                                                  subtask.return_address, subtask.return_port, subtask.key_id,
                                                  subtask.task_owner, self.node_name)

    def run(self):

        if self.counting_task:
            for task_thread in self.current_computations:
                task_thread.check_timeout()
            return

        if self.waiting_for_task == 0 or self.waiting_for_task is None:
            if time.time() - self.last_task_request > self.task_request_frequency:
                if len(self.current_computations) == 0:
                    self.last_task_request = time.time()
                    self.__request_task()
        elif self.use_waiting_ttl:
            time_ = time.time()
            self.waiting_ttl -= time_ - self.last_checking
            self.last_checking = time_
            if self.waiting_ttl < 0:
                self.waiting_for_task = None
                self.waiting_ttl = 0

    def get_progresses(self):
        ret = {}
        for c in self.current_computations:
            tcss = TaskChunkStateSnapshot(c.get_subtask_id(), 0.0, 0.0, c.get_progress(),
                                          c.get_task_short_desc())  # FIXME: cpu power and estimated time left
            ret[c.subtask_id] = tcss

        return ret

    def change_config(self):
        self.dir_manager = DirManager(self.task_server.get_task_computer_root(), self.node_name)
        self.resource_manager = ResourcesManager(self.dir_manager, self)
        self.task_request_frequency = self.task_server.config_desc.task_request_interval
        self.use_waiting_ttl = self.task_server.config_desc.use_waiting_for_task_timeout
        self.waiting_for_task_timeout = self.task_server.config_desc.waiting_for_task_timeout

    def session_timeout(self):
        if self.counting_task:
            return
        else:
            self.waiting_for_task = None
            self.waiting_ttl = 0

    def increase_request_trust(self, subtask_id):
        with self.lock:
            self.increase_trust_val = True

    def __request_task(self):
        self.waiting_ttl = self.waiting_for_task_timeout
        self.last_checking = time.time()
        self.waiting_for_task = self.task_server.request_task()

    def __request_resource(self, task_id, resource_header, return_address, return_port, key_id, task_owner):
        self.waiting_ttl = self.waiting_for_task_timeout
        self.last_checking = time.time()
        self.waiting_for_task = 1
        self.waiting_for_task = self.task_server.request_resource(task_id, resource_header, return_address, return_port,
                                                                  key_id,
                                                                  task_owner)

    def __compute_task(self, subtask_id, docker_images,
                       src_code, extra_data, short_desc, task_timeout):
        task_id = self.assigned_subtasks[subtask_id].task_id
        working_directory = self.assigned_subtasks[subtask_id].working_directory
        self.dir_manager.clear_temporary(task_id)
        if docker_images:
            tt = DockerRunnerThread( self, subtask_id, docker_images,
                                     working_directory, src_code,
                                     extra_data, short_desc,
                                     self.resource_manager.get_resource_dir(task_id),
                                     self.resource_manager.get_temporary_dir(task_id),
                                     task_timeout )
        else:
            tt = PyTaskThread(self, subtask_id, working_directory, src_code,
                              extra_data, short_desc,
                              self.resource_manager.get_resource_dir(task_id),
                              self.resource_manager.get_temporary_dir(task_id),
                              task_timeout)
        tt.setDaemon(True)
        self.current_computations.append(tt)
        tt.start()

    def quit(self):
        for t in self.current_computations:
            t.end_comp()


class AssignedSubTask(object):
    def __init__(self, src_code, extra_data, short_desc, owner_address, owner_port):
        self.src_code = src_code
        self.extra_data = extra_data
        self.short_desc = short_desc
        self.owner_address = owner_address
        self.owner_port = owner_port


class TaskThread(Thread):
    def __init__(self, task_computer, subtask_id, working_directory, src_code, extra_data, short_desc, res_path, tmp_path,
                 timeout=0):
        super(TaskThread, self).__init__()

        self.task_computer = task_computer
        self.vm = None
        self.subtask_id = subtask_id
        self.src_code = src_code
        self.extra_data = extra_data
        self.short_desc = short_desc
        self.result = None
        self.done = False
        self.res_path = res_path
        self.tmp_path = tmp_path
        self.working_directory = working_directory
        self.prev_working_directory = ""
        self.lock = Lock()
        self.error = False
        self.error_msg = ""
        self.use_timeout = timeout != 0
        self.task_timeout = timeout
        self.last_time_checking = time.time()

    def check_timeout(self):
        if not self.use_timeout:
            return
        time_ = time.time()
        self.task_timeout -= time_ - self.last_time_checking
        self.last_time_checking = time_
        if self.task_timeout < 0:
            self.error = True
            self.error_msg = "Timeout"
            self.end_comp()

    def get_subtask_id(self):
        return self.subtask_id

    def get_task_short_desc(self):
        return self.short_desc

    def get_progress(self):
        with self.lock:
            return self.vm.get_progress()

    def get_error(self):
        with self.lock:
            return self.error

    def run(self):
        logger.info("RUNNING ")
        try:
            self.__do_work()
            self.task_computer.task_computed(self)
        except Exception as exc:
            logger.error("Task computing error: {}".format(exc))
            self.error = True
            self.error_msg = str(exc)
            self.done = True
            self.task_computer.task_computed(self)

    def end_comp(self):
        self.vm.end_comp()

    def __do_work(self):
        extra_data = copy(self.extra_data)

        abs_res_path = os.path.abspath(os.path.normpath(self.res_path))
        abs_tmp_path = os.path.abspath(os.path.normpath(self.tmp_path))

        self.prev_working_directory = os.getcwd()
        os.chdir(os.path.join(abs_res_path, os.path.normpath(self.working_directory)))
        try:
            extra_data["resourcePath"] = abs_res_path
            extra_data["tmp_path"] = abs_tmp_path
            self.result = self.vm.run_task(self.src_code, extra_data)
        finally:
            os.chdir(self.prev_working_directory)


class PyTaskThread(TaskThread):
    def __init__(self, task_computer, subtask_id, working_directory, src_code, extra_data, short_desc, res_path,
                 tmp_path, timeout):
        super(PyTaskThread, self).__init__(task_computer, subtask_id, working_directory, src_code, extra_data,
                                           short_desc, res_path, tmp_path, timeout)
        self.vm = PythonProcVM()


class PyTestTaskThread(PyTaskThread):
    def __init__(self, task_computer, subtask_id, working_directory, src_code, extra_data, short_desc, res_path,
                 tmp_path, timeout):
        super(PyTestTaskThread, self).__init__(task_computer, subtask_id, working_directory, src_code, extra_data,
                                               short_desc, res_path, tmp_path, timeout)
        self.vm = PythonTestVM()


class DockerRunnerThread(TaskThread):

    def __init__(self, task_computer, subtask_id, docker_images,
                 working_directory, src_code, extra_data, short_desc,
                 res_path, tmp_path, timeout):
        super(DockerRunnerThread, self).__init__(
            task_computer, subtask_id, working_directory, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)

        assert docker_images
        # Find available image
        self.image = None
        for img in docker_images:
            if img.is_available():
                self.image = img
                break
        self.job = None

    def _fail(self, error_obj):
        logger.error("Task computing error: {}".format(error_obj))
        self.error = True
        self.error_msg = str(error_obj)
        self.done = True
        self.task_computer.task_computed(self)

    def run(self):
        if not self.image:
            self._fail("None of the Docker images is available")
            return
        try:
            params = self.extra_data.copy()
            with DockerJob(self.image, self.src_code, params,
                           self.working_directory,
                           self.res_path, self.tmp_path) as job:
                self.job = job
                self.job.start()
                if self.use_timeout:
                    exit_code = self.job.wait(self.task_timeout)
                else:
                    exit_code = self.job.wait()
                if exit_code == 0:
                    # TODO: this always returns file, implement returning data
                    # TODO: this only collects top-level files, what if there
                    # are output files in subdirs?
                    out_files = [os.path.join(self.tmp_path, f)
                                 for f in os.listdir(self.tmp_path)]
                    out_files = filter(lambda f: os.path.isfile(f), out_files)
                    self.result = {"data": out_files, "result_type": 1}
                self.task_computer.task_computed(self)
        except requests.exceptions.ReadTimeout as exc:
            if self.use_timeout:
                self._fail("Task timed out after {:.1f}s".
                           format(self.task_timeout))
            else:
                self._fail(exc)
        except Exception as exc:
            self._fail(exc)

    def get_progress(self):
        # TODO: make the container update some status file?
        return 0.0

    def end_comp(self):
        pass

    def check_timeout(self):
        pass
