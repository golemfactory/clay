import sys
import uuid

class UploadController(object):
    # TODO add size control logic
    def __init__(self, fs):
        self.fs = fs
        self.meta = {
            'chunk_size': 131072*4,
            'platform': sys.platform
        }
        self.fd_id_map = {}

    def open(self, path, mode):
        _id = str(uuid.uuid4())
        self.fd_id_map[_id] = self.fs.open(path, mode)
        return _id

    def upload(self, _id, data):
        count = self.fd_id_map[_id].write(data)
        if len(data) < self.meta['chunk_size']:
            self.fd_id_map[_id].close()
            del self.fd_id_map[_id]
        return count

    def download(self, _id):
        data = self.fd_id_map[_id].read(self.meta['chunk_size'])
        if len(data) < self.meta['chunk_size']:
            self.fd_id_map[_id].close()
            del self.fd_id_map[_id]
        return data

