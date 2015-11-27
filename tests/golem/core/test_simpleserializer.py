import unittest
from golem.core.simpleserializer import SimpleSerializerDebug, SimpleSerializerRelease, SimpleSerializer


class Example:
    def __init__(self):
        self.int = 4
        self.string = u"abcdefghi\\kwa \\bla"
        self.list = ['a', 'b', 'c']
        self.dict = {'k': None, 'w': 1.0, 'a': 'bla'}

    def __eq__(self, exm2):
        if self.int != exm2.int:
            return False
        if self.string != exm2.string:
            return False
        if self.list != exm2.list:
            return False
        if cmp(self.dict, exm2.dict) != 0:
            return False
        return True


class TestSimpleSerializer(unittest.TestCase):
    def testSerializer(self):
        self.assertTrue(isinstance(SimpleSerializer(), SimpleSerializerRelease))


class TestSimpleSerializerDebug(unittest.TestCase):
    def testSerializer(self):
        data = ['foo', {'bar': ('baz', None, 1.0, 2)}]
        ser = SimpleSerializerDebug.dumps(data)
        self.assertTrue(isinstance(ser, str))
        data2 = SimpleSerializerDebug.loads(ser)
        self.assertTrue(isinstance(data2, list))
        self.assertEqual(len(data2), len(data))


class TestSimpleSerializerRelease(unittest.TestCase):
    def testSerializer(self):
        data = Example()
        ser = SimpleSerializerRelease.dumps(data)
        self.assertTrue(isinstance(ser, str))
        data2 = SimpleSerializerRelease.loads(ser)
        self.assertTrue(isinstance(data2, Example))
        self.assertEqual(data, data2)
