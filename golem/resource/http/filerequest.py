import requests
import os

__all__ = ['DownloadFileRequest', 'DownloadFilesRequest'
                                  'UploadFileRequest', 'UploadFilesRequest']


class Request(object):
    def run(self, url, headers=None, **kwargs):
        pass


class FileRequest(Request):
    def __init__(self, file_path, **kwargs):
        if not file_path:
            raise Exception("Invalid file path")

        self.file_path = file_path
        self.file_name = os.path.basename(self.file_path)


class DownloadFileRequest(FileRequest):
    def __init__(self, file_hash, file_path, stream=True, **kwargs):
        super(DownloadFileRequest, self).__init__(file_path)
        self.file_hash = file_hash
        self.stream = stream

    def run(self, url, headers=None, **kwargs):
        r = requests.get(url + '/' + str(self.file_hash),
                         headers=headers,
                         stream=self.stream)
        r.raise_for_status()

        with open(self.file_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        return self.file_path


class UploadFileRequest(FileRequest):
    def __init__(self, file_path, dst_name, method=None, stream=False, **kwargs):

        super(UploadFileRequest, self).__init__(file_path)
        self.dst_name = dst_name
        self.method = method or 'post'
        self.stream = stream

    def run(self, url, headers=None, **kwargs):
        if os.path.isfile(self.file_path):
            with open(self.file_path, 'rb') as input_file:

                files = dict(
                    file=(
                        self.dst_name,
                        input_file,
                        'application/octet-stream'
                    )
                )

                r = requests.request(self.method, url,
                                     files=files,
                                     headers=headers,
                                     stream=self.stream)
                r.raise_for_status()

                return r.text
        return None


class DeleteFileRequest(Request):
    def __init__(self, file_hash):
        self.file_hash = file_hash

    def run(self, url, headers=None, **kwargs):
        r = requests.delete(url + '/' + self.file_hash,
                            headers=headers)
        r.raise_for_status()
        return r.text
