import binascii
import uuid
import zipfile
from typing import Iterable, Tuple, Optional

import abc
import os

from golem.core.fileencrypt import AESFileEncryptor
from golem.core.fileshelper import common_dir, relative_path
from golem.core.printable_object import PrintableObject
from golem.core.simplehash import SimpleHash
from golem.core.simpleserializer import CBORSerializer


def backup_rename(file_path, max_iterations=100):
    if not os.path.exists(file_path):
        return

    name = None
    counter = 0

    while counter < max(1, max_iterations):
        counter += 1
        name = file_path + '.{}'.format(counter)

        if not os.path.exists(name):
            break
        elif counter == max_iterations:
            name = file_path + '.{}'.format(uuid.uuid4())

    os.rename(file_path, name)


class Packager(object):

    def create(self,
               output_path: str,
               disk_files: Optional[Iterable[str]] = None,
               cbor_files: Optional[Iterable[Tuple[str, str]]] = None,
               **_kwargs):

        if not disk_files and not cbor_files:
            raise ValueError('No files to pack')

        disk_files = self._prepare_file_dict(disk_files)
        with self.generator(output_path) as of:

            if disk_files:
                for file_path, file_name in disk_files.items():
                    self.write_disk_file(of, file_path, file_name)

            if cbor_files:
                for file_name, file_data in cbor_files:
                    cbor_data = CBORSerializer.dumps(file_data)
                    self.write_cbor_file(of, file_name, cbor_data)

        pkg_sha1 = self.write_sha1(output_path, output_path)
        return output_path, pkg_sha1

    @classmethod
    def read_sha1(cls, package_path: str):
        sha1_file_path = package_path + '.sha1'

        with open(sha1_file_path, 'r') as sf:
            return sf.read().strip()

    @classmethod
    def write_sha1(cls, source_path: str, package_path: str):
        sha1_path = package_path + '.sha1'
        pkg_sha1 = SimpleHash.hash_file(source_path)
        pkg_sha1 = binascii.hexlify(pkg_sha1).decode('utf8')

        with open(sha1_path, 'w') as sf:
            sf.write(pkg_sha1)
        return pkg_sha1

    @classmethod
    def _prepare_file_dict(cls, disk_files):
        if len(disk_files) == 1:
            disk_file = next(iter(disk_files))
            prefix = os.path.dirname(disk_file)
        else:
            prefix = common_dir(disk_files)

        return {
            absolute_path: relative_path(absolute_path, prefix)
            for absolute_path in disk_files
        }

    @abc.abstractmethod
    def extract(self, input_path, output_dir=None, **kwargs):
        pass

    @abc.abstractmethod
    def generator(self, output_path):
        pass

    @abc.abstractmethod
    def package_name(self, file_path):
        pass

    @abc.abstractmethod
    def write_disk_file(self, obj, file_path, file_name):
        pass

    @abc.abstractmethod
    def write_cbor_file(self, obj, file_name, cbor_data):
        pass


class ZipPackager(Packager):

    ZIP_MODE = zipfile.ZIP_STORED  # no compression

    def extract(self, input_path, output_dir=None, **kwargs):

        if not output_dir:
            output_dir = os.path.dirname(input_path)
        os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(input_path, 'r', compression=self.ZIP_MODE) as zf:
            zf.extractall(output_dir)
            extracted = zf.namelist()

        return extracted, output_dir

    def generator(self, output_path):
        return zipfile.ZipFile(output_path, mode='w', compression=self.ZIP_MODE)

    def write_disk_file(self, obj, file_path, file_name):
        ZipPackager.zip_append(obj, file_path.rstrip('/'))

    def write_cbor_file(self, obj, file_name, cbord_data):
        obj.writestr(file_name, cbord_data)

    @classmethod
    def package_name(cls, file_path):
        if file_path.lower().endswith('.zip'):
            return file_path
        return file_path + '.zip'

    @staticmethod
    def zip_append(archive, path, subdirectory=""):
        basename = os.path.basename(path)
        if os.path.isdir(path):
            if subdirectory == "":
                subdirectory = basename
            archive.write(path, os.path.join(subdirectory))
            for root, dirs, files in os.walk(path):
                for d in dirs:
                    ZipPackager.zip_append(archive, os.path.join(root, d),
                                           os.path.join(subdirectory, d))
                for f in files:
                    archive.write(os.path.join(root, f),
                                  os.path.join(subdirectory, f))
                break
        elif os.path.isfile(path):
            archive.write(path, os.path.join(subdirectory, basename))
        else:
            raise RuntimeError("Packaging supports only \
                    directories and files, unsupported object: {}".format(path))


class EncryptingPackager(Packager):

    creator_class = ZipPackager
    encryptor_class = AESFileEncryptor

    def __init__(self, secret):
        self._packager = self.creator_class()
        self._secret = secret

    def create(self,
               output_path: str,
               disk_files: Optional[Iterable[str]] = None,
               cbor_files: Optional[Iterable[Tuple[str, str]]] = None,
               **_kwargs):

        tmp_file_path = self.package_name(output_path)
        backup_rename(tmp_file_path)

        pkg_file_path, pkg_sha1 = super().create(tmp_file_path,
                                                 disk_files=disk_files,
                                                 cbor_files=cbor_files)

        self.encryptor_class.encrypt(pkg_file_path, output_path,
                                     secret=self._secret)
        return output_path, pkg_sha1

    def extract(self, input_path, output_dir=None, **kwargs):
        tmp_file_path = self.package_name(input_path)
        backup_rename(tmp_file_path)

        self.encryptor_class.decrypt(input_path, tmp_file_path,
                                     secret=self._secret)
        os.remove(input_path)

        return self._packager.extract(tmp_file_path, output_dir=output_dir)

    def generator(self, output_path):
        return self._packager.generator(output_path)

    def package_name(self, file_path):
        return self.creator_class.package_name(file_path)

    def write_disk_file(self, obj, file_path, file_name):
        self._packager.write_disk_file(obj, file_path, file_name)

    def write_cbor_file(self, obj, file_name, cbor_data):
        self._packager.write_cbor_file(obj, file_name, cbor_data)


class TaskResultPackager:

    def create(self,
               output_path: str,
               disk_files: Optional[Iterable[str]] = None,
               cbor_files: Optional[Iterable[Tuple[str, str]]] = None,
               **kwargs):
        task_result = kwargs.get('task_result')
        disk_files, cbor_files = self.__collect_files(task_result,
                                                      disk_files=disk_files,
                                                      cbor_files=cbor_files)

        return super().create(output_path,
                              disk_files=disk_files,
                              cbor_files=cbor_files)

    def extract(self, input_path, output_dir=None, **kwargs):
        files, files_dir = super().extract(input_path, output_dir=output_dir)  # noqa pylint:disable=no-member

        extracted = ExtractedPackage(files, files_dir)

        return extracted

    @staticmethod
    def __collect_files(result, disk_files=None, cbor_files=None):
        disk_files = disk_files[:] if disk_files else []
        cbor_files = cbor_files[:] if cbor_files else []
        disk_files.extend(result.result)
        return disk_files, cbor_files


class EncryptingTaskResultPackager(TaskResultPackager, EncryptingPackager):
    pass


class ZipTaskResultPackager(TaskResultPackager, ZipPackager):
    pass


class ExtractedPackage(PrintableObject):

    def __init__(self, files=None, files_dir="", result=None):
        self.files = files or []
        self.files_dir = files_dir
        self.result = result

    def to_extra_data(self):
        full_path_files = []

        for filename in self.files:
            full_path = os.path.join(self.files_dir, filename)
            full_path_files.append(full_path)

        extra_data = {
            "result": full_path_files,
        }

        return extra_data
