import random
from threading import Lock

import ovh
import requests

from golem.http.stream import ChunkStream
from golem.resource.http.filerequest import DownloadFileRequest, UploadFileRequest, DeleteFileRequest

ENDPOINT = 'ovh-eu'

GOLEM_STORAGE = 'golemstorage'
SERVICE_NAME = "d915ddf36a7741daad87fd3d8b5e0df3"

CONSUMER_KEY = "nP3MX83oDjCqUykq65eLXZbDRFsIBmaX"

APPLICATION_KEY = "YeXUvlivqiEhzSIb"
APPLICATION_SECRET = "uR3diYfs2cBqY96CR47n23JEMRmC9fxC"


class PatchedDownloadFileRequest(DownloadFileRequest):

    def __init__(self, file_hash, file_path,
                 stream=True, chunk_size=4096, **kwargs):

        super(PatchedDownloadFileRequest, self).__init__(file_hash, file_path, stream, **kwargs)
        self.postfix_len = len('--') + ChunkStream.short_sep_len * 2
        self.chunk_size = chunk_size

    def run(self, url, headers=None, **kwargs):

        response = requests.get(url + '/' + self.file_hash,
                                headers=headers,
                                stream=self.stream)

        response.raise_for_status()
        content_length = int(response.headers['Content-Length'])

        with open(self.file_path, 'wb') as f:
            self._write_to_file(response, f, content_length)
        return self.file_path

    def _write_to_file(self, response, f, content_length):
        data_size = content_length
        data_read = 0

        content_started = False
        done = False
        buf = bytes()

        for chunk in response.iter_content(chunk_size=self.chunk_size):
            if chunk:
                data_read += len(chunk)

            if content_started:
                if chunk and not done:
                    if data_read > data_size:
                        overflow = data_read - data_size
                        chunk = chunk[:-overflow]
                        done = True
                    f.write(chunk)
            else:
                if chunk:
                    buf += chunk

                content_idx = buf.find(ChunkStream.long_sep)
                if content_idx != -1:

                    content_idx += ChunkStream.long_sep_list_len
                    sep_end_idx = buf.find(ChunkStream.short_sep)

                    data_size -= len(buf[:sep_end_idx]) + self.postfix_len

                    if len(buf) >= content_length:
                        f.write(buf[content_idx:data_size])
                    else:
                        f.write(buf[content_idx:])

                    content_started = True


def api_translate_exceptions(method):
    def wrapper(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except (ovh.exceptions.HTTPError,
                ovh.exceptions.NetworkError,
                ovh.exceptions.InvalidResponse,
                ovh.exceptions.InvalidCredential,
                ovh.exceptions.InvalidKey) as exc:
            raise requests.exceptions.HTTPError(exc)
        except:
            raise
    return wrapper


class OpenStackSwiftAPI(object):

    api_lock = Lock()

    token = None
    regions = []
    region_urls = None
    headers = {
        "X-Auth-Token": token,
        "X-Ovh-Application": APPLICATION_KEY,
        "Content-type": "application/json"
    }

    ovh_client = ovh.Client(endpoint=ENDPOINT,
                            application_key=APPLICATION_KEY,
                            application_secret=APPLICATION_SECRET,
                            consumer_key=CONSUMER_KEY)

    @staticmethod
    def is_initialized():
        oss = OpenStackSwiftAPI
        return oss.token and oss.regions

    @staticmethod
    @api_translate_exceptions
    def update_token():
        oss = OpenStackSwiftAPI
        response_json = oss.ovh_client.get('/cloud/project/{}/storage/access'
                                           .format(SERVICE_NAME),
                                           verify=False)
        oss.token = response_json['token']
        oss.headers['X-Auth-Token'] = oss.token
        oss.set_endpoints(response_json['endpoints'])

    @staticmethod
    def set_endpoints(endpoints):
        if not endpoints:
            return

        oss = OpenStackSwiftAPI
        oss.region_urls = {}
        for item in endpoints:
            if 'region' in item and 'url' in item:
                oss.region_urls[item['region']] = item['url']
        oss.regions = oss.region_urls.keys()


def api_access(method):
    oss = OpenStackSwiftAPI

    def wrapper(*args, **kwargs):
        if not oss.is_initialized():
            oss.update_token()
        try:
            return method(*args, **kwargs)
        except requests.exceptions.HTTPError as exc:
            if exc.response.status_code == 401:
                # update access token
                oss.update_token()
                # re-run last request
                return method(*args, **kwargs)
            else:
                raise
    return wrapper


class OpenStackSwiftAPIClient(object):

    @api_access
    def get(self, file_hash, file_path, region):
        url = self._get_url(region)
        req = PatchedDownloadFileRequest(file_hash, file_path, stream=False)

        headers = dict(OpenStackSwiftAPI.headers)
        headers.update({
            'Accept-Encoding': 'gzip, deflate, sdch, identity',
            'Accept': 'application/octet-stream, text/plain',
        })

        return req.run(url, headers=headers)

    @api_access
    def put(self, file_path, dst_name, region):
        url = self._get_url(region) + '/' + dst_name
        req = UploadFileRequest(file_path, dst_name, method='put', stream=False)
        return req.run(url, headers=OpenStackSwiftAPI.headers)

    @api_access
    def delete(self, file_hash, region):
        url = self._get_url(region)
        req = DeleteFileRequest(file_hash)
        return req.run(url, headers=OpenStackSwiftAPI.headers)

    @api_access
    def get_region_url_for_node(self, node_id):
        if node_id:
            total = len(OpenStackSwiftAPI.region_urls)
            c = 0
            for i in node_id:
                c += ord(i)
            return OpenStackSwiftAPI.regions[c % total]
        return random.choice(OpenStackSwiftAPI.regions)

    @api_access
    def _get_url(self, region):
        if region not in OpenStackSwiftAPI.region_urls:
            raise ValueError("Invalid region: {}"
                             .format(region))
        return OpenStackSwiftAPI.region_urls[region] + '/' + GOLEM_STORAGE
