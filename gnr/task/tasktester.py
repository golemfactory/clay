import os
from threading import Lock
import shutil
import logging
from golem.task.taskbase import Task, resource_types
from golem.resource.resource import TaskResourceHeader, decompress_dir
from golem.task.taskcomputer import PyTestTaskThread
from gnr.renderingdirmanager import get_test_task_path, get_test_task_directory, get_tmp_path, get_test_task_tmp_path

logger = logging.getLogger(__name__)

def find_flm(directory):
    if not os.path.exists(directory):
        return None
        
    try:
        for root, dirs, files in os.walk(directory):
            for names in files:
                if names[-4:] == ".flm":
                    return os.path.join(root,names)

    except:
        import traceback
        # Print the stack traceback
        traceback.print_exc()
        return None

class TaskTester:
    def __init__(self, task, root_path, finished_callback):
        assert isinstance(task, Task)
        self.task = task
        self.test_task_res_path = None
        self.tmp_dir = None
        self.success = False
        self.lock = Lock()
        self.tt = None
        self.root_path = root_path
        self.finished_callback = finished_callback

    def run(self):
        try:
            success = self.__prepare_resources()
            self.__prepare_tmp_dir()

            if not success:
                return False

            ctd = self.task.query_extra_data_for_test_task()

            self.tt = PyTestTaskThread(self,
                                       ctd.subtask_id,
                                       ctd.working_directory,
                                       ctd.src_code,
                                       ctd.extra_data,
                                       ctd.short_description,
                                       self.test_task_res_path,
                                       self.tmp_dir,
                                       0)
            self.tt.start()

        except Exception as exc:
            logger.warning("Task not tested properly: {}".format(exc))
            self.finished_callback(False)

    def increase_request_trust(self, subtask_id):
        pass

    def get_progress(self):
        if self.tt:
            with self.lock:
                if self.tt.get_error():
                    logger.warning("Task not tested properly")
                    self.finished_callback(False, error=self.tt.error_msg)
                    return 0
                return self.tt.get_progress()
        return None

    def task_computed(self, task_thread):
        if task_thread.result:
            res, est_mem = task_thread.result
        if task_thread.result and res and res.get("data"):
            logger.info("Test task computation success !")
            
            # Search for flm - the result of testing a lux task
            # It's needed for verification of received results
            flm = find_flm(self.tmp_dir)
            if flm is not None:
                try:
                    filename = "test_result.flm"
                    flm_path = os.path.join(self.tmp_dir, filename)
                    os.rename(flm, flm_path)
                    save_path = get_tmp_path(self.task.header.node_name, self.task.header.task_id, self.task.root_path)
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)
                    
                    shutil.copy(flm_path, save_path)
                except: 
                    logger.warning("Couldn't rename and copy .flm file")

            self.finished_callback(True, est_mem)
        else:
            logger_msg = "Test task computation failed!"
            if task_thread.error_msg:
                logger_msg += " " + task_thread.error_msg
            logger.warning(logger_msg)
            self.finished_callback(False, error=task_thread.error_msg)

    def __prepare_resources(self):

        self.test_task_res_path = get_test_task_path(self.root_path)
        if not os.path.exists(self.test_task_res_path):
            os.makedirs(self.test_task_res_path)
        else:
            shutil.rmtree(self.test_task_res_path, True)
            os.makedirs(self.test_task_res_path)

        self.test_task_res_dir = get_test_task_directory()
        rh = TaskResourceHeader(self.test_task_res_dir)
        res_file = self.task.get_resources(self.task.header.task_id, rh, resource_types["zip"])

        if res_file:
            decompress_dir(self.test_task_res_path, res_file)

        return True

    def __prepare_tmp_dir(self):

        self.tmp_dir = get_test_task_tmp_path(self.root_path)
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)
        else:
            shutil.rmtree(self.tmp_dir, True)
            os.makedirs(self.tmp_dir)

