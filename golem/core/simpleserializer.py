import cPickle  # release version
import json   # debug version

import dill

IS_DEBUG = False  # True - json, False - pickle


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


# class CBORSerializer(object):
#     @classmethod
#     def dumps(cls, obj):
#         return cbor.dumps(obj)
#
#     @classmethod
#     def loads(cls, data):
#         return cbor.loads(data)


class DILLSerializer(object):
    @classmethod
    def dumps(cls, obj):
        return dill.dumps(obj)

    @classmethod
    def loads(cls, data):
        return dill.loads(data)

if IS_DEBUG:
    SimpleSerializer = SimpleSerializerDebug
else:
    SimpleSerializer = SimpleSerializerRelease
