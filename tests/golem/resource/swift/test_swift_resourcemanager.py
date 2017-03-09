import inspect
import os
import unittest
import uuid

import ovh
import requests

from golem.resource.base.resourcetest import AddGetResources
from golem.resource.client import file_multihash
from golem.resource.swift.api import api_translate_exceptions
from golem.resource.swift.resourcemanager import OpenStackSwiftClient, OpenStackSwiftResourceManager
from golem.testutils import TempDirFixture


class TestSwiftClient(TempDirFixture):
    def setUp(self):
        TempDirFixture.setUp(self)

        self.src_file = os.path.join(self.tempdir, 'src_file')
        self.dst_file_name = 'dst_file'
        self.dst_file_path = self.tempdir

        with open(self.src_file, 'w') as f:
            for _ in xrange(100):
                f.write(str(uuid.uuid4()))

    def test(self):
        client = OpenStackSwiftClient()

        max_retries = 10
        for i in xrange(0, max_retries):
            try:
                options = client.build_options('node_id')
            except Exception as exc:
                if i >= max_retries:
                    self.fail("Max retries = {} reached (exception: {})"
                              .format(max_retries, exc))
            else:
                break

        results = client.add(self.src_file,
                             client_options=options)

        result_dict = results[0]

        filename, multihash = result_dict[u'Name'], result_dict[u'Hash']

        assert filename
        assert multihash
        assert client.get_file(multihash,
                               filename=self.dst_file_name,
                               filepath=self.dst_file_path,
                               client_options=options)

        dst_path = os.path.join(self.dst_file_path, self.dst_file_name)

        assert os.stat(self.src_file).st_size == os.stat(dst_path).st_size
        assert file_multihash(self.src_file) == file_multihash(dst_path)

        client.delete(multihash,
                      client_options=options)


class TestSwiftResources(AddGetResources):
    __test__ = True
    _resource_manager_class = OpenStackSwiftResourceManager


class TestTranslateExceptions(unittest.TestCase):

    def test(self):

        excs_to_translate = [ovh.exceptions.HTTPError,
                             ovh.exceptions.NetworkError,
                             ovh.exceptions.InvalidResponse,
                             ovh.exceptions.InvalidCredential,
                             ovh.exceptions.InvalidKey]

        excs_to_skip = [c for n, c in inspect.getmembers(ovh.exceptions)
                        if inspect.isclass(c) and c not in excs_to_translate]

        @api_translate_exceptions
        def wrapped(_exc):
            raise _exc

        for exc in excs_to_translate:
            with self.assertRaises(requests.exceptions.HTTPError):
                wrapped(exc)

        for exc in excs_to_skip:
            try:
                wrapped(exc)
            except requests.exceptions.HTTPError:
                self.fail("Invalid exception translated")
            except:
                pass
