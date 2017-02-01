import random
import unittest

from golem.core.simpleserializer import SimpleSerializer, CBORSerializer, DictCoder, DictSerializer


class Example(object):
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
        data = Example()
        ser = SimpleSerializer.dumps(data)
        self.assertTrue(isinstance(ser, str))
        data2 = SimpleSerializer.loads(ser)
        self.assertTrue(isinstance(data2, Example))
        self.assertEqual(data, data2)


class MockSerializationInnerSubject(object):
    def __init__(self):
        self.property_1 = random.randrange(1, 1 * 10 ** 18)
        self._property_2 = True
        self.property_3 = "string"
        self.property_4 = ['list', 'of', ('items',), [
                              random.randrange(1, 10000),
                              random.randrange(1, 10000),
                              random.randrange(1, 10000)
                          ]]

    def method(self):
        pass

    def __eq__(self, other):
        return self.property_1 == other.property_1 and \
            self.property_3 == other.property_3 and \
            self.property_4 == other.property_4


class MockSerializationSubject(object):
    def __init__(self):
        self.property_1 = dict(k='v', u=MockSerializationInnerSubject())
        self.property_2 = MockSerializationInnerSubject()
        self._property_3 = None
        self.property_4 = ['v', 1, (1, 2, 3), MockSerializationInnerSubject()]

    def method_1(self):
        pass

    def _method_2(self):
        pass

    def __eq__(self, other):
        return self.property_1 == other.property_1 and \
            self.property_2 == other.property_2 and \
            self.property_4 == other.property_4


def assert_properties(first, second):

    assert first.__class__ == second.__class__
    assert first.property_2.__class__ == second.property_2.__class__
    assert first.property_2.__class__ == MockSerializationInnerSubject

    inner = first.property_2

    assert inner.property_1
    assert inner.property_1 == second.property_2.property_1
    assert isinstance(inner.property_3, basestring)
    assert isinstance(inner.property_4, list)


class TestDictSerializer(unittest.TestCase):

    def test_properties(self):
        obj = MockSerializationSubject()
        dict_repr = DictSerializer.dump(obj)

        self.assertTrue('property_1' in dict_repr)
        self.assertTrue('property_2' in dict_repr)
        self.assertFalse('_property_3' in dict_repr)
        self.assertFalse('method_1' in dict_repr)
        self.assertFalse('_method_2' in dict_repr)

        deserialized = DictSerializer.load(dict_repr)
        assert_properties(deserialized, obj)

    def test_serialization_as_class(self):

        obj = MockSerializationSubject()
        dict_repr = DictSerializer.dump(obj)

        self.assertTrue(DictCoder.cls_key in dict_repr)
        self.assertTrue('property_1' in dict_repr)
        self.assertTrue('property_2' in dict_repr)
        self.assertTrue(isinstance(DictSerializer.load(dict_repr), MockSerializationSubject))

        dict_repr = DictSerializer.dump(obj, typed=False)

        self.assertFalse(DictCoder.cls_key in dict_repr)
        self.assertTrue('property_1' in dict_repr)
        self.assertTrue('property_2' in dict_repr)
        self.assertTrue(isinstance(DictSerializer.load(dict_repr), dict))
        self.assertTrue(isinstance(DictSerializer.load(dict_repr, as_class=MockSerializationSubject),
                                   MockSerializationSubject))

    def test_serialization_result(self):
        obj = MockSerializationSubject()
        self.assertEqual(DictSerializer.dump(obj), {u'property_1': {u'k': u'v',
             u'u': {
                 u'property_1': obj.property_1[u'u'].property_1,
                 u'property_3': u'string',
                 u'property_4': [u'list',
                                 u'of',
                                 (u'items',),
                                 obj.property_1[u'u'].property_4[-1]],
                 DictCoder.cls_key: u'test_simpleserializer.MockSerializationInnerSubject'}
             },
             u'property_2': {
                 u'property_1': obj.property_2.property_1,
                 u'property_3': u'string',
                 u'property_4': [u'list',
                                 u'of',
                                 (u'items',),
                                 obj.property_2.property_4[-1]],
                 DictCoder.cls_key: u'test_simpleserializer.MockSerializationInnerSubject'},
             u'property_4': [
                 u'v',
                 1,
                 (1, 2, 3),
                 {
                     u'property_1': obj.property_4[-1].property_1,
                     u'property_3': u'string',
                     u'property_4': [u'list',
                                     u'of',
                                     (u'items',),
                                     obj.property_4[-1].property_4[-1]],
                     DictCoder.cls_key: u'test_simpleserializer.MockSerializationInnerSubject'
                 }
             ],
             DictCoder.cls_key: u'test_simpleserializer.MockSerializationSubject'
        })

        self.assertFalse(DictCoder.cls_key in DictSerializer.dump(obj, typed=False))


class TestCBORSerializer(unittest.TestCase):

    def test(self):
        obj = MockSerializationSubject()
        serialized = CBORSerializer.dumps(obj)
        deserialized = CBORSerializer.loads(serialized)
        assert_properties(deserialized, obj)

