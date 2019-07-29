import os
import re
import shutil
from threading import Lock
from typing import List
from golem.core.fileshelper import copy_file_tree, relative_path


def split_path(path):
    return re.split('/|\\\\', path) if path else path


def norm_path(path):
    normpath = os.path.normpath(path)
    split = os.path.split(normpath)
    while split and split[0] in ['.', '..']:
        split = split[1:]
    return os.path.join(*split) if split else ''


class ResourceError(RuntimeError):
    pass


class Resource:

    __slots__ = ('hash', 'files', 'path', 'res_id')

    def __init__(self, resource_hash, res_id=None, files=None, path=None):
        self.hash = resource_hash
        self.res_id = res_id
        self.files = files
        self.path = path

    def __eq__(self, other):
        return other and \
            self.res_id == other.res_id and \
            self.hash == other.hash and \
            self.path == other.path and \
            self.files == other.files

    def __str__(self):
        return 'Resource(hash: {}, id: {})'.format(self.hash, self.res_id)

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
        # id to resources
        self._id_to_res = dict()
        # id to resource common prefix
        self._id_to_prefix = dict()

    def add_resource(self, resource):
        res_id = resource.res_id

        with self._lock:
            resource_list = self._id_to_res.get(res_id)
            if not resource_list:
                self._id_to_res[res_id] = resource_list = list()
            resource_list.append(resource)

            self._hash_to_res[resource.hash] = resource
            self._path_to_res[resource.path] = resource

    def get_by_hash(self, resource_hash, default=None):
        return self._hash_to_res.get(resource_hash, default)

    def get_by_path(self, resource_path, default=None):
        return self._path_to_res.get(resource_path, default)

    def has_resource(self, resource):
        if resource.res_id and resource.res_id not in self._id_to_res:
            return False
        if resource.hash and resource.hash not in self._hash_to_res:
            return False
        return resource.path in self._path_to_res

    def get_resources(self, res_id, default=None):
        return self._id_to_res.get(res_id, default or [])

    def set_prefix(self, res_id, prefix):
        self._id_to_prefix[res_id] = norm_path(prefix)

    def get_prefix(self, res_id, default=''):
        return self._id_to_prefix.get(res_id, default)

    def remove(self, res_id):
        resources = self._id_to_res.pop(res_id, [])
        for r in resources:
            self._hash_to_res.pop(r.hash, None)
            self._path_to_res.pop(r.path, None)
        self._id_to_prefix.pop(res_id, None)
        return resources

    def clear(self):
        self._hash_to_res = dict()
        self._path_to_res = dict()
        self._id_to_res = dict()
        self._id_to_prefix = dict()


class ResourceStorage(object):

    def __init__(self, dir_manager, resource_dir_method):
        self.dir_manager = dir_manager
        self.resource_dir_method = resource_dir_method
        self.cache = ResourceCache()

    def get_dir(self, res_id):
        return norm_path(self.resource_dir_method(res_id))

    def get_path(self, relative_file_path, res_id):
        resource_dir = self.get_dir(res_id)
        return os.path.join(resource_dir, norm_path(relative_file_path))

    def get_root(self):
        return self.dir_manager.get_node_dir()

    def get_resources(self, res_id) -> List[Resource]:
        return self.cache.get_resources(res_id)

    def exists(self, resource):
        return self.cache.has_resource(resource) and resource.exists

    def relative_path(self, path, res_id):
        path = norm_path(path)
        common_prefix = self.cache.get_prefix(res_id)
        return relative_path(path, common_prefix)

    def copy_dir(self, src_dir):

        root_dir = self.get_root()
        src_dir = norm_path(src_dir)

        if root_dir != src_dir:
            copy_file_tree(src_dir, root_dir)
            return True

    def copy(self, src_path, dst_relative_path, res_id):

        dst_relative_path = norm_path(dst_relative_path)
        dst_path = self.get_path(dst_relative_path, res_id)
        src_path = norm_path(src_path)

        if os.path.isfile(dst_path):
            os.remove(dst_path)
        elif os.path.isdir(dst_path):
            shutil.rmtree(dst_path)

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        if os.path.isfile(src_path):
            shutil.copyfile(src_path, dst_path)
        elif os.path.isdir(src_path):
            copy_file_tree(src_path, dst_path)
        else:
            raise ResourceError("Error reading source path: '{}'"
                                .format(src_path))
