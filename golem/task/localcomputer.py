import logging
import os
import shutil
import stat
import time
from copy import copy
from typing import Callable, Optional
from threading import Lock

from golem_messages.message import ComputeTaskDef

from apps.blender.resources.scenefileeditor import generate_blender_crop_file
from golem.core.common import to_unicode
from golem.core.fileshelper import common_dir
from golem.docker.image import DockerImage
from golem.docker.task_thread import DockerTaskThread
from golem.resource.dirmanager import DirManager

from .taskthread import TaskThread


logger = logging.getLogger("golem.task")


class LocalComputer:
    DEFAULT_WARNING = "Computation failed"
    DEFAULT_SUCCESS = "Task computation success!"

    def __init__(self,
                 root_path: str,
                 success_callback: Callable,
                 error_callback: Callable,
                 get_compute_task_def: Callable[[], ComputeTaskDef] = None,
                 compute_task_def: ComputeTaskDef = None,
                 check_mem: bool = False,
                 comp_failed_warning: str = DEFAULT_WARNING,
                 comp_success_message: str = DEFAULT_SUCCESS,
                 resources: list = None,
                 additional_resources=None) -> None:
        self.res_path = None
        self.tmp_dir: Optional[str] = None
        self.success = False
        self.lock = Lock()
        self.tt: Optional[DockerTaskThread] = None
        self.dir_manager = DirManager(root_path)
        self.compute_task_def = compute_task_def
        self.get_compute_task_def = get_compute_task_def
        self.error_callback = error_callback
        self.success_callback = success_callback
        self.check_mem = check_mem
        self.comp_failed_warning = comp_failed_warning
        self.comp_success_message = comp_success_message
        if resources is None:
            resources = []
        self.resources = resources
        if additional_resources is None:
            additional_resources = []
        self.additional_resources = additional_resources
        self.start_time = None
        self.end_time = None
        self.test_task_res_path: Optional[str] = None

    def run(self) -> None:
        try:
            self.start_time = time.time()
            self._prepare_tmp_dir()
            self._prepare_resources(self.resources)  # makes a copy
            if not self.compute_task_def:
                ctd = self.get_compute_task_def()
            else:
                ctd = self.compute_task_def

            self.tt = self._get_task_thread(ctd)
            self.tt.start().addBoth(lambda _: self.task_computed(self.tt))

        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("%s", self.comp_failed_warning, exc_info=True)
            self.error_callback(exc)

    def end_comp(self) -> bool:
        if self.tt:
            self.tt.end_comp()
            return True
        return False

    def get_progress(self):
        if self.tt:
            with self.lock:
                if self.tt.get_error():
                    logger.warning(self.comp_failed_warning)
                    return 0.0
                return self.tt.get_progress()
        return None

    def task_computed(self, task_thread: TaskThread) -> None:
        self.end_time = time.time()

        if self.is_success(task_thread):
            self.computation_success(task_thread)
        else:
            self.computation_failure(task_thread)

    # This cannot be changed to staticmethod, because it's overriden in
    # a derived class
    # pylint:disable=no-self-use
    def is_success(self, task_thread: TaskThread) -> bool:
        return \
            not task_thread.error \
            and task_thread.result \
            and task_thread.result.get("data")

    def computation_success(self, task_thread: TaskThread) -> None:
        self.success_callback(task_thread.result, self._get_time_spent())

    def computation_failure(self, task_thread: TaskThread) -> None:
        logger_msg = self.comp_failed_warning
        if task_thread.error_msg:
            logger_msg += " " + task_thread.error_msg
        logger.warning(logger_msg)
        self.error_callback(to_unicode(task_thread.error_msg))

    def _get_time_spent(self):
        try:
            return self.end_time - self.start_time
        except TypeError:
            logger.error("Cannot measure execution time")

    def _prepare_resources(self, resources):
        self.test_task_res_path = self.dir_manager.get_task_test_dir("")

        def onerror(func, target_path, exc_info):
            # Try to set write permissions
            if not os.access(target_path, os.W_OK):
                os.chmod(target_path, stat.S_IWUSR)
                func(target_path)
            else:
                raise OSError('Cannot remove {}: {}'
                              .format(target_path, exc_info))

        if os.path.exists(self.test_task_res_path):
            shutil.rmtree(self.test_task_res_path, onerror=onerror)

        if resources:
            if len(resources) == 1 and os.path.isdir(resources[0]):
                shutil.copytree(resources[0], self.test_task_res_path)
            else:
                # no trailing separator
                if len(resources) == 1:
                    base_dir = os.path.dirname(resources[0])
                else:
                    base_dir = common_dir(resources)

                base_dir = os.path.normpath(base_dir)

                for resource in filter(None, resources):
                    norm_path = os.path.normpath(resource)

                    sub_path = norm_path.replace(base_dir + os.path.sep, '', 1)
                    sub_dir = os.path.dirname(sub_path)
                    dst_dir = os.path.join(self.test_task_res_path, sub_dir)
                    os.makedirs(dst_dir, exist_ok=True)

                    name = os.path.basename(resource)
                    shutil.copy2(resource, os.path.join(dst_dir, name))

        for res in self.additional_resources:
            if not os.path.exists(self.test_task_res_path):
                os.makedirs(self.test_task_res_path)
            shutil.copy(res, self.test_task_res_path)

        return True

    def _prepare_tmp_dir(self):
        self.tmp_dir = self.dir_manager.get_task_temporary_dir("")
        if os.path.exists(self.tmp_dir):
            shutil.rmtree(self.tmp_dir, True)
        os.makedirs(self.tmp_dir)

    def _extract_extra_data_from_ctd(self, ctd: ComputeTaskDef) -> dict:
        if ctd['task_type'] == 'Blender':
            extra_data = copy(ctd['extra_data'])
            extra_data['frames'] = ctd['meta_parameters']['frames']
            extra_data['output_format'] = \
                ctd['meta_parameters']['output_format']
            extra_data['script_src'] = generate_blender_crop_file(
                resolution=ctd['meta_parameters']['resolution'],
                borders_x=ctd['meta_parameters']['borders_x'],
                borders_y=ctd['meta_parameters']['borders_y'],
                use_compositing=ctd['meta_parameters']['use_compositing'],
                samples=ctd['meta_parameters']['samples'],
            )
        else:
            raise RuntimeError('Task Type is set to None')
        return extra_data

    def _get_task_thread(self, ctd: ComputeTaskDef) -> DockerTaskThread:
        if self.test_task_res_path is None:
            raise RuntimeError('Resource path is set to None')
        if self.tmp_dir is None:
            raise RuntimeError('Temporary directory is set to None')
        dir_mapping = DockerTaskThread.generate_dir_mapping(
            resources=self.test_task_res_path,
            temporary=self.tmp_dir,
        )
        extra_data = self._extract_extra_data_from_ctd(ctd)

        return DockerTaskThread(
            ctd['subtask_id'],
            ctd['docker_images'],
            ctd['src_code'],
            extra_data,
            dir_mapping,
            0,
            check_mem=self.check_mem,
        )


class ComputerAdapter(object):

    def __init__(self):
        self.computer = None

    # pylint: disable=too-many-arguments
    def start_computation(self, root_path, success_callback, error_callback,
                          compute_task_def, resources, additional_resources):
        self.computer = LocalComputer(root_path=root_path,
                                      success_callback=success_callback,
                                      error_callback=error_callback,
                                      compute_task_def=compute_task_def,
                                      resources=resources,
                                      additional_resources=additional_resources)
        self.computer.run()

    def wait(self):
        if self.computer.tt is not None:
            self.computer.tt.join()
            return True
        return False

    def get_result(self):
        try:
            return self.computer.tt.result
        except AttributeError:
            return None
