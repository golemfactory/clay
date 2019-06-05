import collections
import inspect
import logging
import sys
import types
from abc import ABC, abstractmethod
from enum import Enum

from golem_messages import datastructures

from golem.core.common import to_unicode

logger = logging.getLogger('golem.core.simpleserializer')


class DictCoder:
    cls_key = 'py/object'
    enum_key = 'py/enum'
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
            setattr(obj, k, cls._from_dict_traverse_obj(v))
        return obj

    @classmethod
    def _enum_to_dict(cls, obj: Enum):
        result = dict()
        result[cls.enum_key] = "{}.{}".format(
            cls.module_and_class(obj), obj.name)
        return result

    @classmethod
    def _enum_from_dict(cls, dictionary):
        path = dictionary[cls.enum_key]
        idx1 = path.rfind('.')
        idx2 = path.rfind('.', 0, idx1)

        module_name = path[:idx2]
        cls_name = path[idx2+1:idx1]
        enum_name = path[idx1+1:]

        module = sys.modules[module_name]
        cls = getattr(module, cls_name)
        return getattr(cls, enum_name)

    @classmethod
    def _to_dict_traverse_dict(cls, dictionary, typed=True):
        result = dict()
        for k, v in list(dictionary.items()):
            if (isinstance(k, str) and k.startswith('_')) \
                    or isinstance(v, collections.Callable):
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
                logger.warning(
                    'set/frozenset have known problems with umsgpack: %r',
                    obj,
                )
            return obj.__class__(
                [cls._to_dict_traverse_obj(o, typed) for o in obj]
            )
        elif isinstance(obj, datastructures.Container):
            return obj.to_dict()
        elif isinstance(obj, Enum):
            return cls._enum_to_dict(obj)
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
            if cls.cls_key in obj:
                return cls.obj_from_dict(obj)
            if cls.enum_key in obj:
                return cls._enum_from_dict(obj)
            return cls._from_dict_traverse_dict(obj)
        elif isinstance(obj, str):
            return to_unicode(obj)
        elif isinstance(obj, collections.Iterable):
            return obj.__class__([cls._from_dict_traverse_obj(o) for o in obj])
        return obj

    @classmethod
    def _is_builtin(cls, obj):
        # pylint: disable=unidiomatic-typecheck
        return type(obj) in cls.builtin_types \
            and not isinstance(obj, types.InstanceType)

    @staticmethod
    def module_and_class(obj):
        fmt = '{}.{}'
        if inspect.isclass(obj):
            return fmt.format(obj.__module__, obj.__name__)
        return fmt.format(obj.__module__, obj.__class__.__name__)


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


class DictSerializable(ABC):

    @abstractmethod
    def to_dict(self) -> dict:
        """ Convert the object to a dict containing only primitive types. """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def from_dict(data: dict) -> 'DictSerializable':
        """ Construct object from a dict containing only primitive types. """
        raise NotImplementedError
