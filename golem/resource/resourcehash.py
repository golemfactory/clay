import os
import hashlib
import base64


class ResourceHash:
    def __init__(self, resource_dir):
        self.resource_dir = resource_dir

    def split_file(self, filename, block_size=2 ** 20):
        with open(filename, "rb") as f:
            file_list = []
            while True:
                data = f.read(block_size)
                if not data:
                    break

                filehash = os.path.join(self.resource_dir, self.__count_hash(data))
                filehash = os.path.normpath(filehash)

                with open(filehash, "wb") as fwb:
                    fwb.write(data)

                file_list.append(filehash)
        return file_list

    def connect_files(self, file_list, res_file):
        with open(res_file, 'wb') as f:
            for file_hash in file_list:
                with open(file_hash, "rb") as fh:
                    while True:
                        data = fh.read()
                        if not data:
                            break
                        f.write(data)

    def get_file_hash(self, filename):
        with open(filename, "rb") as f:
            data = f.read()
            hash_ = self.__count_hash(data)
        return hash_

    def set_resource_dir(self, resource_dir):
        self.resource_dir = resource_dir

    def __count_hash(self, data):
        sha = hashlib.sha1()
        sha.update(data)
        return base64.urlsafe_b64encode(sha.digest())
