import collections
import inspect
import logging
import sys
import types

import cbor2
import jsonpickle
import pytz

from golem.core.common import to_unicode

logger = logging.getLogger('golem.core.simpleserializer')


class DictCoder(object):

    cls_key = u'py/object'
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

        _idx = cls_path.rfind(u'.')
        module_name, cls_name = cls_path[:_idx], cls_path[_idx+1:]
        module = sys.modules[module_name]
        sub_cls = getattr(module, cls_name)

        obj = sub_cls.__new__(sub_cls)

        for k, v in dictionary.iteritems():
            if cls._is_class(v):
                setattr(obj, k, cls.obj_from_dict(v))
            else:
                setattr(obj, k, cls._from_dict_traverse_obj(v))
        return obj

    @classmethod
    def _to_dict_traverse_dict(cls, dictionary, typed=True):
        result = dict()
        for k, v in dictionary.iteritems():
            if (isinstance(k, basestring) and k.startswith('_')) or callable(v):
                continue
            result[unicode(k)] = cls._to_dict_traverse_obj(v, typed)
        return result

    @classmethod
    def _to_dict_traverse_obj(cls, obj, typed=True):
        if isinstance(obj, dict):
            return cls._to_dict_traverse_dict(obj, typed)
        elif isinstance(obj, basestring):
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
        for k, v in dictionary.iteritems():
            result[k] = cls._from_dict_traverse_obj(v)
        return result

    @classmethod
    def _from_dict_traverse_obj(cls, obj):
        if isinstance(obj, dict):
            if cls._is_class(obj):
                return cls.obj_from_dict(obj)
            return cls._from_dict_traverse_dict(obj)
        elif isinstance(obj, basestring):
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
        fmt = u'{}.{}'
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


class SimpleSerializer(object):
    """ Simple meta-class that serialize and deserialize objects to a json format"""
    @classmethod
    def dumps(cls, obj):
        """
        Serialize obj to a JSON format
        :param obj: object to be serialized
        :return str: serialized object in json format
        """
        return jsonpickle.dumps(obj)

    @classmethod
    def loads(cls, data):
        """
        Deserialize data to a Python object
        :param str data: json object to be deserialized
        :return: deserialized Python object
        """
        return jsonpickle.loads(data)


class DictSerializer(object):
    """ Serialize and deserialize objects to a dictionary"""
    @staticmethod
    def dump(obj, typed=True):
        """
        Serialize obj to dictionary
        :param obj: object to be serialized
        :param bool typed: simple serialization does not include type information
        :return str: serialized object in json format
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
        return cbor2.dumps(obj, encoders=cls.encoders, datetime_as_timestamp=True, timezone=pytz.utc)
