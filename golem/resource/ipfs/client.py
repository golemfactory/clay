import json
import logging
import os
import shutil
import tarfile
import uuid
from functools import wraps
from threading import Lock
from types import FunctionType

import ipfsApi
import requests
from ipfsApi.commands import ArgCommand
from ipfsApi.http import HTTPClient, pass_defaults
from twisted.internet import reactor
from twisted.internet import threads

logger = logging.getLogger(__name__)

__all__ = ['IPFSCommands', 'IPFSClient', 'IPFSAsyncCall', 'IPFSAsyncExecutor', 'StreamFileObject']


class StreamFileObject:

    def __init__(self, source):
        self.source = source
        self.source_iter = None

    def read(self, count):
        if not self.source_iter:
            self.source_iter = self.source.iter_content(count)

        try:
            return self.source_iter.next()
        except StopIteration:
            return None


class ChunkedHTTPClient(HTTPClient):

    lock = Lock()
    chunk_size = 1024

    """
    Class implements a workaround for the download method,
    which hangs on reading http response stream data.
    """

    @pass_defaults
    def download(self, path, args=[], opts={},
                 filepath=None, filename=None,
                 compress=False, archive=True, **kwargs):
        """
        Downloads a file from IPFS to the directory given by :filepath:
        Support for :filename: was added (which replaces file's hash)
        """
        method = 'get'
        multihash = args[0]

        url = self.base + path
        work_dir = filepath or '.'
        params = [('stream-channels', 'true')]

        if compress:
            params += [('compress', 'true')]
            archive = True
        if archive:
            params += [('archive', 'true')]

        for opt in opts.items():
            params.append(opt)
        for arg in args:
            params.append(('arg', arg))

        if self._session:
            res = self._session.request(method, url,
                                        params=params, stream=True,
                                        **kwargs)
        else:
            res = requests.request(method, url,
                                   params=params, stream=True,
                                   **kwargs)

        res.raise_for_status()

        if archive:
            stream = StreamFileObject(res)
            mode = 'r|gz' if compress else 'r|'
            with tarfile.open(fileobj=stream, mode=mode) as tar_file:
                return self._tar_extract(tar_file, work_dir,
                                         filename, multihash)
        else:
            return self._write_file(res, work_dir, filename, multihash)

    @classmethod
    def _tar_extract(cls, tar_file, work_dir, filename, multihash):

        dst_path = os.path.join(work_dir, filename)
        tmp_dir = os.path.join(work_dir, str(uuid.uuid4()))
        tmp_path = os.path.join(tmp_dir, multihash)

        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        with cls.lock:
            if os.path.exists(dst_path):
                os.remove(dst_path)

        tar_file.extractall(tmp_dir)

        if os.path.exists(tmp_path):
            with cls.lock:
                shutil.move(tmp_path, dst_path)

            shutil.rmtree(tmp_dir, ignore_errors=True)
            cls.__log_downloaded(filename, multihash, dst_path)
            return filename, multihash

        return None, None

    @classmethod
    def _write_file(cls, res, work_dir, filename, multihash):
        dst_path = os.path.join(work_dir, filename)
        with open(dst_path, 'wb') as f:
            for chunk in res.iter_content(cls.chunk_size, False):
                if chunk:
                    f.write(chunk)

        cls.__log_downloaded(filename, multihash, dst_path)
        return filename, multihash

    @classmethod
    def __log_downloaded(cls, filename, multihash, dst_path):
        logger.debug("IPFS: downloaded {} ({}) to {}"
                     .format(filename, multihash, dst_path))


def parse_response(resp):

    """ Returns python objects from a string """
    result = []

    if resp:
        if isinstance(resp, basestring):
            parsed = parse_response_entry(resp)
            if parsed:
                result.append(parsed)
        elif isinstance(resp, list):
            for sub_resp in resp:
                if sub_resp:
                    result.extend(parse_response(sub_resp))
        else:
            result.append(resp)

    return result


def parse_response_entry(entry):
    parts = entry.split('\n')
    result = []

    for part in parts:
        if part:
            try:
                result.append(json.loads(part))
            except ValueError:
                result.append(part)

    return result


def response_wrapper(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        return parse_response(func(*args, **kwargs))
    return wrapped


class IPFSCommands(object):
    pin = 0
    unpin = 1
    add = 2
    pull = 3
    id = 4


class IPFSClientMetaClass(type):

    """ IPFS api client methods decorated with response wrappers """

    def __new__(mcs, class_name, bases, class_dict):
        new_dict = {}
        all_items = class_dict.items()

        for base in bases:
            all_items.extend(base.__dict__.items())

        for name, attribute in all_items:
            if type(attribute) == FunctionType and not name.startswith('_'):
                if name in class_dict:
                    attribute = class_dict.get(name)
                attribute = response_wrapper(attribute)
            new_dict[name] = attribute

        instance = type.__new__(mcs, class_name, bases, new_dict)
        instance._clientfactory = ChunkedHTTPClient

        return instance


class IPFSClient(ipfsApi.Client):

    """ Class of ipfsApi.Client methods decorated with response wrapper """

    __metaclass__ = IPFSClientMetaClass

    _clientfactory = ChunkedHTTPClient

    def __init__(self,
                 host=None,
                 port=None,
                 base=None,
                 default_enc='json',
                 **defaults):

        super(IPFSClient, self).__init__(host=host, port=port,
                                         base=base, default_enc=default_enc,
                                         **defaults)

        self._refs_local = ArgCommand('/refs/local')

    def refs_local(self, **kwargs):
        return self._refs_local.request(self._client, **kwargs)

    def get_file(self, multihash, **kwargs):
        return self._get.request(self._client, multihash, **kwargs)

    def get(self, multihash, **kwargs):
        raise NotImplementedError("Please use the get_file method")


class IPFSAsyncCall(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs if kwargs else {}


class IPFSAsyncExecutor(object):

    """ Execute a deferred job in a separate thread (Twisted) """
    reactor.suggestThreadPoolSize(reactor.getThreadPool().max + 4)

    @classmethod
    def run(cls, deferred_call, success, error):
        deferred = threads.deferToThread(deferred_call.method,
                                         *deferred_call.args,
                                         **deferred_call.kwargs)
        deferred.addCallbacks(success, error)

