import collections
import inspect
import json
import logging
import sys
import types
from abc import ABCMeta, abstractmethod
from typing import Optional, Type, Union

import cbor2
import pytz
from rlp import Serializable

from golem.core.common import to_unicode

logger = logging.getLogger('golem.core.simpleserializer')


class DictCoder:
    cls_key = 'py/object'
    deep_serialization = True
    builtin_types = [i for i in types.__dict__.values() if isinstance(i, type)]

    @classmethod
    def to_dict(cls, obj, typed=True):
        return cls._to_dict_traverse_obj(obj, typed)

    @classmethod
    def from_dict(cls, dictionary, as_class=None):
        if as_class:
            dictionary = dict(dictionary)
            dictionary[cls.cls_key] = cls.module_and_class(as_class)
        return cls._from_dict_traverse_obj(dictionary)

    @classmethod
    def obj_to_dict(cls, obj, typed=True):
        """Stores object's public properties in a dictionary"""
        result = cls._to_dict_traverse_dict(obj.__dict__, typed)
        if typed:
            result[cls.cls_key] = cls.module_and_class(obj)
        return result

    @classmethod
    def obj_from_dict(cls, dictionary):
        cls_path = dictionary.pop(cls.cls_key)

        _idx = cls_path.rfind('.')
        module_name, cls_name = cls_path[:_idx], cls_path[_idx+1:]
        module = sys.modules[module_name]
        sub_cls = getattr(module, cls_name)

        obj = sub_cls.__new__(sub_cls)

        for k, v in list(dictionary.items()):
            if cls._is_class(v):
                setattr(obj, k, cls.obj_from_dict(v))
            else:
                setattr(obj, k, cls._from_dict_traverse_obj(v))
        return obj

    @classmethod
    def _to_dict_traverse_dict(cls, dictionary, typed=True):
        result = dict()
        for k, v in list(dictionary.items()):
            if (isinstance(k, str) and k.startswith('_')) or isinstance(v, collections.Callable):
                continue
            result[str(k)] = cls._to_dict_traverse_obj(v, typed)
        return result

    @classmethod
    def _to_dict_traverse_obj(cls, obj, typed=True):
        if isinstance(obj, dict):
            return cls._to_dict_traverse_dict(obj, typed)
        elif isinstance(obj, str):
            return to_unicode(obj)
        elif isinstance(obj, collections.Iterable):
            if isinstance(obj, (set, frozenset)):
                logger.warning('set/frozenset have known problems with umsgpack: %r', obj)
            return obj.__class__([cls._to_dict_traverse_obj(o, typed) for o in obj])
        elif cls.deep_serialization:
            if hasattr(obj, '__dict__') and not cls._is_builtin(obj):
                return cls.obj_to_dict(obj, typed)
        return obj

    @classmethod
    def _from_dict_traverse_dict(cls, dictionary):
        result = dict()
        for k, v in list(dictionary.items()):
            result[k] = cls._from_dict_traverse_obj(v)
        return result

    @classmethod
    def _from_dict_traverse_obj(cls, obj):
        if isinstance(obj, dict):
            if cls._is_class(obj):
                return cls.obj_from_dict(obj)
            return cls._from_dict_traverse_dict(obj)
        elif isinstance(obj, str):
            return to_unicode(obj)
        elif isinstance(obj, collections.Iterable):
            return obj.__class__([cls._from_dict_traverse_obj(o) for o in obj])
        return obj

    @classmethod
    def _is_class(cls, obj):
        return isinstance(obj, dict) and cls.cls_key in obj

    @classmethod
    def _is_builtin(cls, obj):
        return type(obj) in cls.builtin_types and not isinstance(obj, types.InstanceType)

    @staticmethod
    def module_and_class(obj):
        fmt = '{}.{}'
        if inspect.isclass(obj):
            return fmt.format(obj.__module__, obj.__name__)
        return fmt.format(obj.__module__, obj.__class__.__name__)


class CBORCoder(DictCoder):

    tag = 0xef
    # Leave nested and special object serialization to CBOR
    deep_serialization = False
    disable_value_sharing = True

    @classmethod
    def encode(cls, encoder, value, fp):
        if value is not None:
            obj_dict = cls.obj_to_dict(value)
            encoder.encode_semantic(cls.tag, obj_dict, fp,
                                    disable_value_sharing=cls.disable_value_sharing)

    @classmethod
    def decode(cls, decoder, value, fp, shareable_index=None):
        obj = cls.obj_from_dict(value)
        # As instructed in cbor2.CBORDecoder
        if shareable_index is not None and not cls.disable_value_sharing:
            decoder.shareables[shareable_index] = obj
        return obj


class DictSerializer(object):
    """ Serialize and deserialize objects to a dictionary"""
    @staticmethod
    def dump(obj, typed=True):
        """
        Serialize obj to dictionary
        :param obj: object to be serialized
        :param typed: simple serialization does not include type information
        :return: serialized object in json format
        """
        return DictCoder.to_dict(obj, typed=typed)

    @staticmethod
    def load(dictionary, as_class=None):
        """
        Deserialize dictionary to a Python object
        :param as_class: create a specified class instance
        :param dict dictionary: dictionary to deserialize
        :return: deserialized Python object
        """
        return DictCoder.from_dict(dictionary, as_class=as_class)


class CBORSerializer(object):
    """ Serialize and deserialize objects to and from CBOR"""
    decoders = dict()
    decoders[CBORCoder.tag] = CBORCoder.decode
    encoders = {(object, CBORCoder.encode)}

    @classmethod
    def loads(cls, payload):
        return cbor2.loads(payload, semantic_decoders=cls.decoders)

    @classmethod
    def dumps(cls, obj):
        return cbor2.dumps(
            obj,
            encoders=cls.encoders,
            datetime_as_timestamp=True,
            timezone=pytz.utc
        )


class DictSerializable(metaclass=ABCMeta):
    @abstractmethod
    def to_dict(self) -> dict:
        "Converts the object to a dict containing only primitive types"

    @staticmethod
    @abstractmethod
    def from_dict(data: Optional[dict]) -> 'DictSerializable':
        "Converts the object to a dict containing only primitive types"


class JSONDictSerializer:
    @staticmethod
    def loads(data: Union[bytes, str], key_type: Type) -> dict:
        """
        Creates a dict from the JSON formatted data.
        :param data: the JSON data
        :param key_type: the type the keys should be converted to
        """
        deserialized = json.loads(data)
        return {key_type(k): v for k, v in deserialized.items()}

    @staticmethod
    def dumps(obj) -> str:
        """
        Dumps the object obj to JSON, if can be easily serialied
        """
        return json.dumps(obj)

class CBORSedes(Serializable):

    def __init__(self):
        Serializable.__init__(self)

    @classmethod
    def serialize(cls, obj):
        return CBORSerializer.dumps(obj)


    @classmethod
    def deserialize(cls, serial, exclude=None, **kwargs):
        return CBORSerializer.loads(serial)
