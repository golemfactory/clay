import abc
import os
import uuid
import zipfile

from golem.core.fileencrypt import AESFileEncryptor
from golem.core.simpleserializer import CBORSerializer
from golem.task.taskbase import result_types


class Packager(object):

    def create(self, output_path, disk_files=None, cbor_files=None, **kwargs):

        if not disk_files and not cbor_files:
            raise ValueError('No files to pack')

        with self.generator(output_path) as of:

            if disk_files:
                for file_path in disk_files:
                    file_name = os.path.basename(file_path)
                    self.write_disk_file(of, file_path, file_name)

            if cbor_files:
                for file_name, file_data in cbor_files:
                    cbor_data = CBORSerializer.dumps(file_data)
                    self.write_cbor_file(of, file_name, cbor_data)

        return output_path

    @abc.abstractmethod
    def extract(self, input_path, output_dir=None, **kwargs):
        pass

    @abc.abstractmethod
    def generator(self, output_path):
        pass

    @abc.abstractmethod
    def write_disk_file(self, obj, file_path, file_name):
        pass

    @abc.abstractmethod
    def write_cbor_file(self, obj, file_name, cbor_data):
        pass


class ZipPackager(Packager):

    def extract(self, input_path, output_dir=None, **kwargs):

        if not output_dir:
            output_dir = os.path.dirname(input_path)

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        with zipfile.ZipFile(input_path, 'r') as zf:
            zf.extractall(output_dir)
            extracted = zf.namelist()

        return extracted, output_dir

    def generator(self, output_path):
        return zipfile.ZipFile(output_path, mode='w')

    def write_disk_file(self, obj, file_path, file_name):
        obj.write(file_path, file_name)

    def write_cbor_file(self, obj, file_name, cbord_data):
        obj.writestr(file_name, cbord_data)


class EncryptingPackager(Packager):

    creator_class = ZipPackager
    encryptor_class = AESFileEncryptor

    def __init__(self, key_or_secret):

        self._creator = self.creator_class()
        self.key_or_secret = key_or_secret

    def create(self, output_path, disk_files=None, cbor_files=None, **kwargs):

        output_dir = os.path.dirname(output_path)
        pkg_file_path = os.path.join(output_dir, str(uuid.uuid4()) + ".pkg")
        out_file_path = super(EncryptingPackager, self).create(pkg_file_path,
                                                               disk_files=disk_files,
                                                               cbor_files=cbor_files)

        self.encryptor_class.encrypt(out_file_path,
                                     output_path,
                                     self.key_or_secret)
        return output_path

    def extract(self, input_path, output_dir=None, **kwargs):

        input_dir = os.path.dirname(input_path)
        tmp_file_path = os.path.join(input_dir, str(uuid.uuid4()) + ".dec")

        self.encryptor_class.decrypt(input_path,
                                     tmp_file_path,
                                     self.key_or_secret)

        os.remove(input_path)
        os.rename(tmp_file_path, input_path)

        return self._creator.extract(input_path, output_dir=output_dir)

    def generator(self, output_path):
        return self._creator.generator(output_path)

    def write_disk_file(self, obj, file_path, file_name):
        self._creator.write_disk_file(obj, file_path, file_name)

    def write_cbor_file(self, obj, file_name, cbord_data):
        self._creator.write_cbor_file(obj, file_name, cbord_data)


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

    descriptor_file_name = '.package_desc'
    result_file_name = '.result_cbor'

    def __init__(self, key_or_secret):
        self.parent = super(EncryptingTaskResultPackager, self)
        self.parent.__init__(key_or_secret)

    def create(self, output_path,
               disk_files=None, cbor_files=None,
               node=None, task_result=None, **kwargs):

        disk_files, cbor_files = self.__collect_files(task_result,
                                                      disk_files=disk_files,
                                                      cbor_files=cbor_files)

        descriptor = TaskResultDescriptor(node, task_result)
        cbor_files.append((self.descriptor_file_name, descriptor))

        return self.parent.create(output_path,
                                  disk_files=disk_files,
                                  cbor_files=cbor_files)

    def extract(self, input_path, output_dir=None, **kwargs):

        files, files_dir = self.parent.extract(input_path, output_dir=output_dir)
        descriptor_path = os.path.join(files_dir, self.descriptor_file_name)

        try:
            with open(descriptor_path, 'rb') as src:
                descriptor = CBORSerializer.loads(src.read())
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

            with open(result_path, 'rb') as src:
                extracted.result = src.read()
            os.remove(result_path)

        return extracted

    def __collect_files(self, result, disk_files=None, cbor_files=None):

        disk_files = disk_files[:] if disk_files else []
        cbor_files = cbor_files[:] if cbor_files else []

        if result.result_type == result_types['data']:
            cbor_files.append((self.result_file_name, result.result))
        elif result.result_type == result_types['files']:
            disk_files.extend(result.result)
        else:
            raise ValueError("Invalid result type {}".format(result.result_type))

        return disk_files, cbor_files


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

        result_type = self.descriptor.result_type
        extra_data = {
            "subtask_id": self.descriptor.subtask_id,
            "result_type": self.descriptor.result_type
        }

        if result_type == result_types['files']:
            extra_data["result"] = full_path_files
        elif result_type == result_types['data']:
            extra_data["result"] = self.result

        if self.result:
            extra_data["data_type"] = "result"

        return extra_data
