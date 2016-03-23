import os
import unittest
import uuid

from golem.resource.dirmanager import DirManager
from golem.resource.ipfs.client import IPFSClient, parse_response_entry, StreamFileObject, parse_response
from golem.tools.testdirfixture import TestDirFixture


class TestIpfsClient(TestDirFixture):

    node_name = 'test_suite'
    task_id = 'deadbeef-deadbeef'

    def setUp(self):
        TestDirFixture.setUp(self)

        self.dir_manager = DirManager(self.path, self.node_name)

        res_path = self.dir_manager.get_task_resource_dir(self.task_id)
        self.test_dir = os.path.join(res_path, 'test_dir')
        self.test_dir_file = os.path.join(self.test_dir, 'dir_file')

        if not os.path.isdir(self.test_dir):
            os.mkdir(self.test_dir)

        with open(self.test_dir_file, 'w') as f:
            f.write("test content")

    def testAdd(self):
        client = IPFSClient()
        client.add([self.test_dir_file])

    def testGetFile(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        tmp_filename = 'tmp_file'
        dest_path = os.path.join(self.test_dir, tmp_filename)

        client.get_file(response[0]['Hash'],
                        filepath=dest_path,
                        filename=tmp_filename)

    def testPinAdd(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(response[0]['Hash'])

    def testPinRm(self):
        client = IPFSClient()
        response = client.add([self.test_dir_file])

        self.assertIsNotNone(response)

        client.pin_add(response[0]['Hash'])
        client.pin_rm(response[0]['Hash'])

class TestParseResponseEntry(unittest.TestCase):
    def test(self):
        json_str = '{"a": [12, 1, 0]}'
        other_str = '{ Something ]'

        self.assertEqual(type(other_str), type(parse_response_entry(other_str)[0]))
        self.assertEqual(dict, type(parse_response_entry(json_str)[0]))


class TestParseResponse(unittest.TestCase):

    def test(self):
        valid_response = '[{"a":"b"}, {"b":1}]'
        other_response = 'Something else'

        response_obj = [[{u"a": u"b"}, {u"b": 1}]]
        other_obj = [['Something else']]
        parsed = parse_response(valid_response)[0]

        self.assertEqual(response_obj, parsed)
        self.assertEqual(other_obj, parse_response(other_response))


class TestStreamFileObject(unittest.TestCase):

    class MockIterator:
        def __init__(self, src, chunk):
            self.src = src
            self.len = len(src)
            self.chunk = chunk
            self.pos = 0

        def __iter__(self):
            return self

        def next(self):
            prev_pos = self.pos
            self.pos += self.chunk

            if prev_pos > self.len:
                raise StopIteration
            else:
                new_pos = max(prev_pos, self.len - self.pos)
                return self.src[prev_pos:new_pos]

    class MockIterable:
        def __init__(self, src):
            self.iterator = None
            self.src = src

        def iter_content(self, chunk):
            if not self.iterator:
                self.iterator = TestStreamFileObject.MockIterator(self.src, chunk)
            return self.iterator

    def test(self):
        src = ''
        for i in xrange(1, 100):
            src = str(uuid.uuid4())

        iterable = self.MockIterable(src)
        so = StreamFileObject(iterable)

        try:
            so.read(32)
        except StopIteration:
            pass
