import os
import unittest
import uuid

from golem.resource.client import file_multihash

from golem.resource.http.resourcesmanager import HTTPResourceManagerClient
from golem.testutils import TempDirFixture


class TestHTTPClient(TempDirFixture):
    def setUp(self):
        TempDirFixture.setUp(self)

        self.src_file = os.path.join(self.tempdir, 'src_file')
        self.dst_file_name = 'dst_file'
        self.dst_file_path = self.tempdir

        with open(self.src_file, 'w') as f:
            for _ in xrange(100):
                f.write(str(uuid.uuid4()))

    @unittest.skip("Test for a legacy server")
    def test(self):
        client = HTTPResourceManagerClient()
        options = client.build_options('node_id')
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
