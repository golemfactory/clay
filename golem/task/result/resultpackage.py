import abc
import os
import pickle
import zipfile

from golem.core.fileencrypt import AESFileEncryptor
from golem.task.taskbase import result_types


class Packager(object):

    def create(self, output_path, disk_files=None, pickle_files=None):

        if not disk_files and not pickle_files:
            raise ValueError('No files to package')

        with self.generator(output_path) as of:

            if disk_files:
                for file_path in disk_files:
                    file_name = os.path.basename(file_path)
                    self.write_disk_file(of, file_path, file_name)

            if pickle_files:
                for file_name, file_data in pickle_files:
                    pickled_data = pickle.dumps(file_data)
                    self.write_pickle_file(of, file_name, pickled_data)

        return output_path

    @abc.abstractmethod
    def extract(self, input_path):
        pass

    @abc.abstractmethod
    def generator(self, output_path):
        pass

    @abc.abstractmethod
    def write_disk_file(self, obj, file_path, file_name):
        pass

    @abc.abstractmethod
    def write_pickle_file(self, obj, file_name, pickled_data):
        pass


class ZipPackager(Packager):

    def extract(self, input_path):
        output_dir = os.path.dirname(input_path)

        with zipfile.ZipFile(input_path, 'r') as zf:
            zf.extractall(output_dir)
            extracted = zf.namelist()

        return extracted, output_dir

    def generator(self, output_path):
        return zipfile.ZipFile(output_path, mode='w')

    def write_disk_file(self, obj, file_path, file_name):
        obj.write(file_path, file_name)

    def write_pickle_file(self, obj, file_name, pickled_data):
        obj.writestr(file_name, pickled_data)


class EncryptingPackager(Packager):

    creator_class = ZipPackager
    encryptor_class = AESFileEncryptor

    def __init__(self, key_or_secret):

        self._creator = self.creator_class()
        self.key_or_secret = key_or_secret

    def create(self, output_path, disk_files=None, pickle_files=None):

        out_file_path = super(EncryptingPackager, self).create(output_path,
                                                               disk_files=disk_files,
                                                               pickle_files=pickle_files)
        tmp_file_path = out_file_path + ".enc"

        self.encryptor_class.encrypt(out_file_path,
                                     tmp_file_path,
                                     self.key_or_secret)

        os.remove(out_file_path)
        os.rename(tmp_file_path, out_file_path)

        return out_file_path

    def extract(self, input_path):

        tmp_file_path = input_path + ".dec"

        self.encryptor_class.decrypt(input_path,
                                     tmp_file_path,
                                     self.key_or_secret)

        os.remove(input_path)
        os.rename(tmp_file_path, input_path)

        return self._creator.extract(input_path)

    def generator(self, output_path):
        return self._creator.generator(output_path)

    def write_disk_file(self, obj, file_path, file_name):
        self._creator.write_disk_file(obj, file_path, file_name)

    def write_pickle_file(self, obj, file_name, pickled_data):
        self._creator.write_pickle_file(obj, file_name, pickled_data)


class TaskResultDescriptor(object):

    def __init__(self, node, task_result):
        self.node_name = node.node_name
        self.node_key_id = node.key

        self.result_type = task_result.result_type
        self.task_id = task_result.task_id
        self.subtask_id = task_result.subtask_id
        self.owner_key_id = task_result.owner_key_id
        self.owner = task_result.owner


class EncryptingTaskResultPackager(EncryptingPackager):

    descriptor_file_name = 'package.desc'
    result_file_name = 'result.pickle'

    def __init__(self, key_or_secret):
        self.parent = super(EncryptingTaskResultPackager, self)
        self.parent.__init__(key_or_secret)

    def create(self, output_path, node, task_result,
               disk_files=None, pickle_files=None):

        disk_files, pickle_files = self.__collect_files(task_result,
                                                        disk_files=disk_files,
                                                        pickle_files=pickle_files)

        descriptor = TaskResultDescriptor(node, task_result)
        pickle_files.append((self.descriptor_file_name, descriptor))

        return self.parent.create(output_path,
                                  disk_files=disk_files,
                                  pickle_files=pickle_files)

    def extract(self, input_path):
        files, files_dir = self.parent.extract(input_path)

        try:
            descriptor_path = os.path.join(files_dir, self.descriptor_file_name)

            with open(descriptor_path, 'r') as src:
                descriptor = pickle.loads(src.read())

            os.remove(descriptor_path)

        except Exception as e:
            raise ValueError('Invalid package descriptor %r' % e.message)

        if self.descriptor_file_name in files:
            files.remove(self.descriptor_file_name)
        if self.result_file_name in files:
            files.remove(self.result_file_name)

        extracted = ExtractedPackage(files, files_dir, descriptor)

        if descriptor.result_type == result_types['data']:

            result_path = os.path.join(files_dir, self.result_file_name)

            with open(result_path, 'r') as src:
                extracted.result = src.read()
            os.remove(result_path)

        return extracted

    def __collect_files(self, result, disk_files=None, pickle_files=None):

        disk_files = disk_files[:] if disk_files else []
        pickle_files = pickle_files[:] if pickle_files else []

        if result.result_type == result_types['data']:
            pickle_files.append((self.result_file_name, result.result))
        elif result.result_type == result_types['files']:
            disk_files.extend(result.result)
        else:
            raise ValueError("Invalid result type {}".format(result.result_type))

        return disk_files, pickle_files


class ExtractedPackage:

    def __init__(self, files=None, files_dir="", descriptor=None, result=None):
        self.files = files or []
        self.files_dir = files_dir
        self.descriptor = descriptor
        self.result = result

    def to_extra_data(self):

        full_path_files = []

        for filename in self.files:
            full_path = os.path.join(self.files_dir, filename)
            full_path_files.append(full_path)

        extra_data = {
            "subtask_id": self.descriptor.subtask_id,
            "result_type": self.descriptor.result_type,
            "result": full_path_files
        }

        if self.result:
            extra_data["data_type"] = "result"

        return extra_data
