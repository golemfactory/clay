from enum import Enum
import random
import unittest

from golem.core.simpleserializer import \
    DictCoder, DictSerializer


class MockSerializationInnerSubject(object):
    def __init__(self):
        self.property_1 = random.randrange(1, 1 * 10 ** 18)
        self._property_2 = True
        self.property_3 = "string"
        self.property_4 = [
            'list', 'of', ('items', ), [
                random.randrange(1, 10000),
                random.randrange(1, 10000),
                random.randrange(1, 10000)
            ]
        ]

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


class MockEnum(Enum):
    Name1 = "value1"
    Name2 = 2


def assert_properties(first, second):

    assert first.__class__ == second.__class__
    assert first.property_2.__class__ == second.property_2.__class__
    assert first.property_2.__class__ == MockSerializationInnerSubject

    inner = first.property_2

    assert inner.property_1
    assert inner.property_1 == second.property_2.property_1
    assert isinstance(inner.property_3, str)
    assert isinstance(inner.property_4, list)


class TestDictSerializer(unittest.TestCase):

    def test_properties(self) -> None:
        obj = MockSerializationSubject()
        dict_repr = DictSerializer.dump(obj)

        self.assertTrue('property_1' in dict_repr)
        self.assertTrue('property_2' in dict_repr)
        self.assertFalse('_property_3' in dict_repr)
        self.assertFalse('method_1' in dict_repr)
        self.assertFalse('_method_2' in dict_repr)

        deserialized = DictSerializer.load(dict_repr)
        assert_properties(deserialized, obj)

    def test_serialization_as_class(self) -> None:

        obj = MockSerializationSubject()
        dict_repr = DictSerializer.dump(obj)

        self.assertTrue(DictCoder.cls_key in dict_repr)
        self.assertTrue('property_1' in dict_repr)
        self.assertTrue('property_2' in dict_repr)
        self.assertTrue(isinstance(
            DictSerializer.load(dict_repr),
            MockSerializationSubject
        ))

        dict_repr = DictSerializer.dump(obj, typed=False)

        self.assertFalse(DictCoder.cls_key in dict_repr)
        self.assertTrue('property_1' in dict_repr)
        self.assertTrue('property_2' in dict_repr)
        self.assertTrue(isinstance(DictSerializer.load(dict_repr), dict))
        self.assertTrue(isinstance(
            DictSerializer.load(dict_repr, as_class=MockSerializationSubject),
            MockSerializationSubject
        ))

    def test_enum_serialization(self):
        dict_repr = DictSerializer.dump(MockEnum.Name1)

        assert len(dict_repr) == 1
        assert "py/enum" in dict_repr
        assert dict_repr["py/enum"].endswith(".MockEnum.Name1")

        assert DictSerializer.load(dict_repr) == MockEnum.Name1

    def test_serialization_result(self):
        obj = MockSerializationSubject()
        self.assertEqual(
            DictSerializer.dump(obj), {
                'property_1': {
                    'k': 'v',
                    'u': {
                        'property_1':
                        obj.property_1['u'].property_1,
                        'property_3':
                        'string',
                        'property_4': [
                            'list', 'of', ('items', ),
                            obj.property_1['u'].property_4[-1]
                        ],
                        DictCoder.cls_key: (
                            'tests.golem.core.test_simpleserializer'
                            '.MockSerializationInnerSubject'
                        )
                    }
                },
                'property_2': {
                    'property_1':
                    obj.property_2.property_1,
                    'property_3':
                    'string',
                    'property_4':
                    ['list', 'of', ('items', ), obj.property_2.property_4[-1]],
                    DictCoder.cls_key: (
                        'tests.golem.core.test_simpleserializer'
                        '.MockSerializationInnerSubject'
                    )
                },
                'property_4': [
                    'v', 1, (1, 2, 3), {
                        'property_1':
                        obj.property_4[-1].property_1,
                        'property_3':
                        'string',
                        'property_4': [
                            'list', 'of', ('items', ),
                            obj.property_4[-1].property_4[-1]
                        ],
                        DictCoder.cls_key: (
                            'tests.golem.core.test_simpleserializer'
                            '.MockSerializationInnerSubject'
                        )
                    }
                ],
                DictCoder.cls_key: (
                    'tests.golem.core.test_simpleserializer'
                    '.MockSerializationSubject'
                )
            })

        self.assertFalse(
            DictCoder.cls_key in DictSerializer.dump(obj, typed=False)
        )
