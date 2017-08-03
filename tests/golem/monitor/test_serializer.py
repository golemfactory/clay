import json
from collections import OrderedDict
from unittest import TestCase

from golem.monitor.serialization.defaultserializer import dict2json
from golem.monitor.serialization.defaultserializer import serialize


class TestDefaultSerializer(TestCase):
    def test_dict2json(self):
        dictionary = OrderedDict([('a', 1), ('b', 2)])
        expected = '{\n    "a": 1,\n    "b": 2\n}'
        self.assertEqual(dict2json(dictionary), expected)

    def test_serialize(self):
        class Dummy:
            a = 1
            b = 2
        expected = '{"obj": {}, "type": "test_str"}'
        self.assertEqual(
            json.loads(serialize('test_str', Dummy())),
            json.loads(expected)
        )
