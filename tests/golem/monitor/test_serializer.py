from unittest import TestCase

from golem.monitor.serialization.defaultserializer import dict2json
from golem.monitor.serialization.defaultserializer import serialize


class TestDefaultSerializer(TestCase):
    def test_dict2json(self):
        expected = '{\n    "a": 1, \n    "b": 2\n}'
        self.assertEquals(dict2json({'a': 1, 'b': 2}), expected)

    def test_serialize(self):
        class Dummy:
            a = 1
            b = 2
        expected = '{"obj": {}, "type": "test_str"}'
        self.assertEquals(serialize('test_str', Dummy()), expected)
