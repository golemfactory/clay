import os
import logging
import shutil

from golem.core.simpleexccmd import is_windows

logger = logging.getLogger(__name__)


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


class DirManager(object):
    """ Manage working directories for application. Return paths, create them if it's needed """
    def __init__(self, root_path, node_name, tmp="tmp", res="resources", output="output", global_resource="golemres"):
        """ Creates new dir manager instance
        :param str root_path: path to the main directory where all other working directories are placed
        :param node_name: current node id
        :param str tmp: temporary directory name
        :param res: resource directory name
        :param output: output directory name
        :param global_resource: global resources directory name
        """
        self.root_path = root_path
        self.node_name = node_name
        self.tmp = tmp
        self.res = res
        self.output = output
        self.global_resource = global_resource
        if is_windows():
            self.__get_path = self.__get_path_windows

    def clear_dir(self, d, undeletable=None):
        """ Remove everything but undeletable from given directory
        :param str d: directory that should be cleared
        :param list undeletable: files and directories to skip while deleting
        """
        if undeletable is None:
            undeletable = []
        if not os.path.isdir(d):
            return
        for i in os.listdir(d):
            path = os.path.join(d, i)
            if path not in undeletable:
                if os.path.isfile(path):
                    os.remove(path)
                if os.path.isdir(path):
                    self.clear_dir(path, undeletable)
                    if os.listdir(path) == []:
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
            return self.__get_path(full_path)
        elif create:
            self.create_dir(full_path)
            return self.__get_path(full_path)
        else:
            logger.error(err_msg)
            return ""

    def get_resource_dir(self, create=True):
        """ Get global resource directory
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_global_resource_path()
        return self.get_dir(full_path, create, "resource dir does not exist")

    def get_task_temporary_dir(self, task_id, create=True):
        """ Get temporary directory
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_tmp_path(task_id)
        return self.get_dir(full_path, create, "temporary dir does not exist")

    def get_task_resource_dir(self, task_id, create=True):
        """ Get task resource directory
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_res_path(task_id)
        return self.get_dir(full_path, create, "resource dir does not exist")

    def get_task_output_dir(self, task_id, create=True):
        """ Get task output directory
        :param bool create: *Default: True* should directory be created if it doesn't exist
        :return str: path to directory
        """
        full_path = self.__get_out_path(task_id)
        return self.get_dir(full_path, create, "output dir does not exist")

    def clear_temporary(self, task_id, undeletable=[]):
        """ Remove everything from temporary directory for given task
        :param task_id: temporary directory of a task with that id should be cleared
        :param undeletable is list of files/directories which shouldn't be removed
        """
        self.clear_dir(self.__get_tmp_path(task_id), undeletable)

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
        return os.path.join(self.root_path, self.node_name, task_id, self.tmp)

    def __get_res_path(self, task_id):
        return os.path.join(self.root_path, self.node_name, task_id, self.res)

    def __get_out_path(self, task_id):
        return os.path.join(self.root_path, self.node_name, task_id, self.output)

    def __get_global_resource_path(self):
        return os.path.join(self.root_path, self.global_resource)

    def __get_path(self, path):
        return path

    def __get_path_windows(self, path):
        return path.replace("\\", "/")
