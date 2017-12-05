import os
import re
import shutil
from threading import Lock

from golem.core.fileshelper import copy_file_tree


def split_path(path):
    return re.split('/|\\\\', path) if path else path


def norm_path(path):
    normpath = os.path.normpath(path)
    split = os.path.split(normpath)
    while split and split[0] in ['.', '..']:
        split = split[1:]
    return os.path.join(*split) if split else ''


class Resource:

    __slots__ = ('hash', 'files', 'path', 'task_id')

    def __init__(self, resource_hash, task_id=None, files=None, path=None):
        self.hash = resource_hash
        self.task_id = task_id
        self.files = files
        self.path = path

    def __eq__(self, other):
        return other and \
            self.task_id == other.task_id and \
            self.hash == other.hash and \
            self.path == other.path and \
            self.files == other.files

    def __str__(self):
        return 'Resource(hash: {}, task: {})'.format(self.hash, self.task_id)

    def __repr__(self):
        return str(self)

    def __len__(self):
        return len(self.files) if self.files else 0

    @property
    def exists(self):
        return all(os.path.exists(os.path.join(self.path, f))
                   for f in self.files)

    def serialize(self):
        return [self.hash, [split_path(path) for path in self.files]]

    @staticmethod
    def deserialize(serialized):
        s_hash, s_files = serialized[:2]
        files = [os.path.join(*split) for split in s_files if split]
        if files:
            return s_hash, files


class ResourceCache(object):

    def __init__(self):
        self._lock = Lock()
        # hash to resource
        self._hash_to_res = dict()
        # path to resource
        self._path_to_res = dict()
        # task to resources
        self._task_to_res = dict()
        # task to resource common prefix
        self._task_to_prefix = dict()

    def add_resource(self, resource):
        task_id = resource.task_id

        with self._lock:
            resource_list = self._task_to_res.get(task_id)
            if not resource_list:
                self._task_to_res[task_id] = resource_list = list()
            resource_list.append(resource)

            self._hash_to_res[resource.hash] = resource
            self._path_to_res[resource.path] = resource

    def get_by_hash(self, resource_hash, default=None):
        return self._hash_to_res.get(resource_hash, default)

    def get_by_path(self, resource_path, default=None):
        return self._path_to_res.get(resource_path, default)

    def has_resource(self, resource):
        if resource.task_id and resource.task_id not in self._task_to_res:
            return False
        if resource.hash and resource.hash not in self._hash_to_res:
            return False
        return resource.path in self._path_to_res

    def get_resources(self, task_id, default=None):
        return self._task_to_res.get(task_id, default or [])

    def set_prefix(self, task_id, prefix):
        self._task_to_prefix[task_id] = norm_path(prefix)

    def get_prefix(self, task_id, default=''):
        return self._task_to_prefix.get(task_id, default)

    def remove(self, task_id):
        resources = self._task_to_res.pop(task_id, [])
        for r in resources:
            self._hash_to_res.pop(r.hash, None)
            self._path_to_res.pop(r.path, None)
        self._task_to_prefix.pop(task_id, None)
        return resources

    def clear(self):
        self._hash_to_res = dict()
        self._path_to_res = dict()
        self._task_to_res = dict()
        self._task_to_prefix = dict()


class ResourceStorage(object):

    def __init__(self, dir_manager, resource_dir_method):
        self.dir_manager = dir_manager
        self.resource_dir_method = resource_dir_method
        self.cache = ResourceCache()

    def get_dir(self, task_id):
        return norm_path(self.resource_dir_method(task_id))

    def get_path(self, relative_file_path, task_id):
        resource_dir = self.get_dir(task_id)
        return os.path.join(resource_dir, norm_path(relative_file_path))

    def get_root(self):
        return self.dir_manager.get_node_dir()

    def get_resources(self, task_id) -> Resource:
        return self.cache.get_resources(task_id)

    def exists(self, resource):
        return self.cache.has_resource(resource) and resource.exists

    def relative_path(self, path, task_id):

        path = norm_path(path)
        common_prefix = self.cache.get_prefix(task_id)

        if path.startswith(common_prefix):
            return_path = path.replace(common_prefix, '', 1)
        else:
            return_path = path

        if common_prefix:
            while return_path and return_path.startswith(os.path.sep):
                return_path = return_path[len(os.path.sep):]

        return return_path

    def copy_dir(self, src_dir):

        root_dir = self.get_root()
        src_dir = norm_path(src_dir)

        if root_dir != src_dir:
            copy_file_tree(src_dir, root_dir)
            return True

    def copy(self, src_path, dst_relative_path, task_id):

        dst_relative_path = norm_path(dst_relative_path)
        dst_path = self.get_path(dst_relative_path, task_id)
        src_path = norm_path(src_path)

        if os.path.isfile(dst_path):
            os.remove(dst_path)
        elif os.path.isdir(dst_path):
            shutil.rmtree(dst_path)

        os.makedirs(dst_path, exist_ok=True)

        if os.path.isfile(src_path):
            shutil.copyfile(src_path, dst_path)
        elif os.path.isdir(src_path):
            copy_file_tree(src_path, dst_path)
        else:
            raise ValueError("Error reading source path: '{}'"
                             .format(src_path))
