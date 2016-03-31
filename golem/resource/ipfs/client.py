from types import FunctionType
from functools import wraps

import os
import json
import tarfile
import requests
import ipfsApi
import shutil
import uuid

from threading import Lock
from twisted.internet import threads
from ipfsApi.http import HTTPClient, pass_defaults
from ipfsApi.commands import ArgCommand

import logging
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

    """
    Class implements a workaround for the download method,
    which hangs on reading http response stream data.
    """

    @pass_defaults
    def download(self, path,
                 filepath=None,
                 filename=None,
                 args=[], opts={},
                 compress=True, **kwargs):
        """
        Downloads a file or files from IPFS into the current working
        directory, or the directory given by :filepath:.

        Support for :filename: was added (which replaces file's hash)
        """
        url = self.base + path
        wd = filepath or '.'

        params = []
        params.append(('stream-channels', 'true'))
        params.append(('archive', 'true'))
        if compress:
            params.append(('compress', 'true'))

        for opt in opts.items():
            params.append(opt)
        for arg in args:
            params.append(('arg', arg))

        method = 'get'
        mode = 'r|gz' if compress else 'r|'

        if self._session:
            res = self._session.request(method, url,
                                        params=params, stream=True, **kwargs)
        else:
            res = requests.request(method, url,
                                   params=params, stream=True, **kwargs)

        res.raise_for_status()
        fileobj = StreamFileObject(res)

        with tarfile.open(fileobj=fileobj, mode=mode) as tar_file:
            return self._tar_extract(tar_file, wd, filename,
                                     multihash=args[0])

    @staticmethod
    def _tar_extract(tar_file, work_dir, filename, multihash):

        dest_path = os.path.join(work_dir, filename)
        tmp_dir = os.path.join(work_dir, str(uuid.uuid4()))
        result = (filename, multihash)

        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)

        for member in tar_file:
            tar_file.extract(member, tmp_dir)

        with ChunkedHTTPClient.lock:
            if os.path.exists(dest_path):
                if os.path.isdir(dest_path):
                    return result
                else:
                    os.remove(dest_path)

            shutil.move(os.path.join(tmp_dir, multihash), dest_path)
            shutil.rmtree(tmp_dir, ignore_errors=True)

        logger.debug("IPFS downloaded %s (%s) to %s" % (filename, multihash, dest_path))
        return result


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


class IPFSAsyncCall(object):

    """ Deferred job descriptor """

    def __init__(self, method, *args, **kwargs):
        self.method = method
        self.args = args
        self.kwargs = kwargs if kwargs else {}


class IPFSAsyncExecutor(object):

    """ Execute a deferred job in a separate thread (Twisted) """

    @classmethod
    def run(cls, deferred_call, success, error):
        deferred = threads.deferToThread(deferred_call.method,
                                         *deferred_call.args,
                                         **deferred_call.kwargs)
        deferred.addCallbacks(success, error)
