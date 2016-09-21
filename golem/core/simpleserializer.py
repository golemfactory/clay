import cPickle  # release version
import collections
import json   # debug version

import types


import cbor2
import dill
import pytz
import sys


IS_DEBUG = False  # True - json, False - CBOR


class SimpleSerializerDebug(object):
    """ Simple meta-class that serialize and deserialize objects to a json format"""
    @classmethod
    def dumps(cls, obj):
        """
        Serialize obj to a JSON format
        :param obj: object to be serialized
        :return str: serialized object in json format
        """
        return json.dumps(obj)

    @classmethod
    def loads(cls, data):
        """
        Deserialize data to a Python object
        :param str data: json object to be deserialized
        :return: deserialized Python object
        """
        return json.loads(data)


class SimpleSerializerRelease(object):
    """ Simple meta-class that serialize and deserialize objects to a pickle representation."""
    @classmethod
    def dumps(cls, obj):
        """
        Serialize obj to a pickle representation
        :param obj: object to be serialized
        :return str: serialized object in a pickle representation
        """
        return cPickle.dumps(obj)

    @classmethod
    def loads(cls, data):
        """
        Deserialize data to a Python object
        :param str data: pickle representation to be deserialized
        :return: deserialized Python object
        """
        return cPickle.loads(data)


class DILLSerializer(object):
    @classmethod
    def dumps(cls, obj):
        return dill.dumps(obj)

    @classmethod
    def loads(cls, data):
        return dill.loads(data)


class CBORCoder(object):

    tag = 0xef
    cls_key = '_cls'
    disable_value_sharing = True
    builtin_types = [i for i in types.__dict__.values() if isinstance(i, type)]

    @classmethod
    def encode(cls, encoder, value, fp):
        if value is not None:
            obj_dict = cls._obj_to_dict(value)
            encoder.encode_semantic(cls.tag, obj_dict, fp,
                                    disable_value_sharing=cls.disable_value_sharing)

    @classmethod
    def decode(cls, decoder, value, fp, shareable_index=None):
        obj = cls._obj_from_dict(value)
        # As instructed in cbor2.CBORDecoder
        if shareable_index is not None and not cls.disable_value_sharing:
            decoder.shareables[shareable_index] = obj
        return obj

    @classmethod
    def _obj_to_dict(cls, obj):
        """Stores object's public properties in a dictionary. Does not support cyclic references"""
        result = cls._to_dict_traverse_dict(obj.__dict__)
        result[cls.cls_key] = cls._module_and_class(obj)
        return result

    @classmethod
    def _obj_from_dict(cls, dictionary):
        module_name, cls_name = dictionary.pop(cls.cls_key)
        module = sys.modules[module_name]

        sub_cls = getattr(module, cls_name)
        obj = sub_cls.__new__(sub_cls)

        for k, v in dictionary.iteritems():
            if cls._is_class(v):
                setattr(obj, k, cls._obj_from_dict(v))
            else:
                setattr(obj, k, cls._from_dict_traverse_obj(v))
        return obj

    @classmethod
    def _to_dict_traverse_dict(cls, dictionary):
        result = dict()
        for k, v in dictionary.iteritems():
            if k.startswith('_') or callable(v):
                continue
            result[k] = cls._to_dict_traverse_obj(v)
        return result

    @classmethod
    def _to_dict_traverse_obj(cls, obj):
        if isinstance(obj, dict):
            return cls._to_dict_traverse_dict(obj)
        elif isinstance(obj, basestring):
            return obj
        elif isinstance(obj, collections.Iterable):
            return obj.__class__([cls._to_dict_traverse_obj(o) for o in obj])
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
                return cls._obj_from_dict(obj)
            return cls._from_dict_traverse_dict(obj)
        elif isinstance(obj, basestring):
            return obj
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
    def _module_and_class(obj):
        return obj.__module__, obj.__class__.__name__


class CBORSerializer(object):

    decoders = dict()
    decoders[CBORCoder.tag] = CBORCoder.decode
    encoders = {(object, CBORCoder.encode)}

    @classmethod
    def loads(cls, payload):
        return cbor2.loads(payload, semantic_decoders=cls.decoders)

    @classmethod
    def dumps(cls, obj):
        return cbor2.dumps(obj, encoders=cls.encoders, datetime_as_timestamp=True, timezone=pytz.utc)


if IS_DEBUG:
    SimpleSerializer = SimpleSerializerDebug
else:
    SimpleSerializer = CBORSerializer
