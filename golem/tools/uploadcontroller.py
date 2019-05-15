import sys
import uuid


class UploadController(object):
    # TODO https://github.com/golemfactory/golem/issues/4157
    def __init__(self, fs):
        self.fs = fs
        self.meta = {
            # This is empirically chosen big enough value (512kB)
            # that works with autobahn
            'chunk_size': 131072*4,
            'platform': sys.platform,
            'syspath': fs.getsyspath('')
        }
        self.fd_id_map = {}

    def open(self, path, mode):
        id_ = str(uuid.uuid4())
        self.fd_id_map[id_] = self.fs.open(path, mode)
        return id_

    def upload(self, id_, data):
        count = self.fd_id_map[id_].write(data)
        if len(data) < self.meta['chunk_size']:
            self.fd_id_map[id_].close()
            del self.fd_id_map[id_]
        return count

    def download(self, id_):
        data = self.fd_id_map[id_].read(self.meta['chunk_size'])
        if len(data) < self.meta['chunk_size']:
            self.fd_id_map[id_].close()
            del self.fd_id_map[id_]
        return data
