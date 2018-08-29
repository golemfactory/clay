import logging
import os
import shutil
import time
from typing import Iterator

logger = logging.getLogger(__name__)


# copied from docker_luxtask.py - difficult to refactor, since
# docker_luxtask.py can't use external dependencies
# the solution would be to replicate code_dir behaviour from dummytask
# in lux task
def symlink_or_copy(source, target):
    try:
        os.symlink(source, target)
    except OSError:
        if os.path.isfile(source):
            if os.path.exists(target):
                os.remove(target)
            shutil.copy(source, target)
        else:
            from distutils import dir_util
            dir_util.copy_tree(source, target, update=1)

# complementary to symlink_or_copy
def rmlink_or_rmtree(target):
    try:
        os.unlink(target)
    except OSError:
        if os.path.isfile(target):
            os.remove(target)
        else:
            shutil.rmtree(target)


def split_path(path):
    """ Split given path into a list of directories
    :param str path: path that should be split
    :return list: list of directories on a given path
    """
    head, tail = os.path.split(path)
    if not tail:
        return []
    if not head:
        return [tail]
    return split_path(head) + [tail]


def find_task_script(task_dir, script_name):
    scripts_path = os.path.abspath(os.path.join(task_dir, "resources", "scripts"))
    script_file = os.path.join(scripts_path, script_name)
    if os.path.isfile(script_file):
        return script_file

    logger.error("Script file {} does not exist!".format(script_file))


def list_dir_recursive(dir: str) -> Iterator[str]:
    for dirpath, dirnames, filenames in os.walk(dir, followlinks=True):
        for name in filenames:
            yield os.path.join(dirpath, name)


class DirManager(object):
    """ Manage working directories for application. Return paths, create them if it's needed """
    def __init__(self, root_path, tmp="tmp", res="resources", output="output", global_resource="golemres", reference_data_dir="reference_data", test="test"):
        """ Creates new dir manager instance
        :param str root_path: path to the main directory where all other working directories are placed
        :param str tmp: temporary directory name
        :param res: resource directory name
        :param output: output directory name
        :param global_resource: global resources directory name
        """
        self.root_path = root_path
        self.tmp = tmp
        self.res = res
        self.output = output
        self.global_resource = global_resource
        self.ref = reference_data_dir
        self.test = test

    def get_file_extension(self, fullpath):
        filename, file_extension = os.path.splitext(fullpath)
        return file_extension

    def clear_dir(self, d, older_than_seconds: int = 0):
        """ Remove everything from given directory
        :param str d: directory that should be cleared
        :param older_than_seconds: delete contents, that are older than given
                                   amount of seconds.
        """
        if not os.path.isdir(d):
            return

        current_time_seconds = time.time()
        min_allowed_mtime = current_time_seconds - older_than_seconds

        for i in os.listdir(d):
            path = os.path.join(d, i)

            if older_than_seconds > 0:
                mtime = os.path.getmtime(path)
                if mtime > min_allowed_mtime:
                    continue

            if os.path.isfile(path):
                os.remove(path)
            if os.path.isdir(path):
                self.clear_dir(path)
                if not os.listdir(path):
                    shutil.rmtree(path, ignore_errors=True)

    def create_dir(self, full_path):
        """ Create new directory, remove old directory if it exists.
        :param str full_path: path to directory that should be created
        """
        if os.path.exists(full_path):
            os.remove(full_path)

        os.makedirs(full_path)

    def get_dir(self, full_path, create, err_msg):
        """ Return path to a give directory if it exists. If it doesn't exist and option create is set to False
        than return nothing and write given error message to a log. If it's set to True, create a directory and return
        it's path
        :param str full_path: path to directory should be checked or created
        :param bool create: if directory doesn't exist, should it be created?
        :param str err_msg: what should be written to a log if directory doesn't exists and create is set to False?
        :return:
        """
        if os.path.isdir(full_path):
            return full_path
        elif create:
            self.create_dir(full_path)
            return full_path
        else:
            logger.error(err_msg)
            return ""

    def get_node_dir(self, create=True):
        """ Get node's directory
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_node_path()
        return self.get_dir(full_path, create, "resource dir does not exist")

    def get_resource_dir(self, create=True):
        """ Get global resource directory
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_global_resource_path()
        return self.get_dir(full_path, create, "resource dir does not exist")

    def get_task_temporary_dir(self, task_id, create=True):
        """ Get temporary directory
        :param task_id:
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_tmp_path(task_id)
        return self.get_dir(full_path, create, "temporary dir does not exist")

    def get_task_resource_dir(self, task_id, create=True):
        """ Get task resource directory
        :param task_id:
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_res_path(task_id)
        return self.get_dir(full_path, create, "resource dir does not exist")

    def get_task_output_dir(self, task_id, create=True):
        """ Get task output directory
        :param task_id:
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_out_path(task_id)
        return self.get_dir(full_path, create, "output dir does not exist")

    def get_ref_data_dir(self, task_id, create=True, counter=None):
        """ Get directory for storing reference data created by the requestor for validation of providers results
        :param task_id:
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_ref_path(task_id, counter)
        return self.get_dir(full_path, create, "reference dir does not exist")

    def get_task_test_dir(self, task_id, create=True):
        """ Get task test directory
        :param task_id:
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_test_path(task_id)
        return self.get_dir(full_path, create, "test dir does not exist")

    @staticmethod
    def list_dir_names(task_dir):
        """ Get the names of subdirectories as task ids
        :param task_dir: Task temporary / resource / output directory
        :return list: list of task ids
        """
        if os.path.isdir(task_dir):
            return next(os.walk(task_dir))[1]
        return []

    def clear_temporary(self, task_id):
        """ Remove everything from temporary directory for given task
        :param task_id: temporary directory of a task with that id should be cleared
        """
        self.clear_dir(self.__get_tmp_path(task_id))

    def clear_resource(self, task_id):
        """ Remove everything from resource directory for given task
        :param task_id: resource directory of a task with that id should be cleared
        """
        self.clear_dir(self.__get_res_path(task_id))

    def clear_output(self, task_id):
        """ Remove everything from output directory for given task
        :param task_id: output directory of a task with that id should be cleared
        """
        self.clear_dir(self.__get_out_path(task_id))

    def __get_tmp_path(self, task_id):
        return os.path.join(self.root_path, task_id, self.tmp)

    def __get_res_path(self, task_id):
        return os.path.join(self.root_path, task_id, self.res)

    def __get_out_path(self, task_id):
        return os.path.join(self.root_path, task_id, self.output)

    def __get_node_path(self):
        return os.path.join(self.root_path)

    def __get_global_resource_path(self):
        return os.path.join(self.root_path, self.global_resource)

    def __get_ref_path(self, task_id, counter):
        return os.path.join(self.root_path, task_id, self.ref, "".join(["runNumber", str(counter)]))

    def __get_test_path(self, task_id):
        return os.path.join(self.root_path, task_id, self.test)


class DirectoryType(object):

    DISTRIBUTED = 1
    RECEIVED = 2
