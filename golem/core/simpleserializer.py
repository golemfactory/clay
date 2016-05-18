import json   # debug version
import cPickle  # release version
import logging

import sys
import traceback

IS_DEBUG = False  # True - json, False - pickle

logger = logging.getLogger(__name__)


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


class SimpleDiagnosticsSerializer(SimpleSerializerRelease):

    threshold = 5000  # log if size / len is greater than threshold

    @classmethod
    def dumps(cls, obj):
        size = sys.getsizeof(obj)
        if size >= cls.threshold:
            logger.debug("dumps: {}".format(size))
            logger.debug("trace: {}".format(traceback.format_stack()[0]))
        return super(SimpleDiagnosticsSerializer, cls).dumps(obj)

    @classmethod
    def loads(cls, data):
        size = len(data)
        if size >= cls.threshold:
            logger.debug("loads: {}".format(size))
            logger.debug("trace: {}".format(traceback.format_stack()[0]))
            logger.debug("source: {}".format(data))
        return super(SimpleDiagnosticsSerializer, cls).loads(data)


if IS_DEBUG:
    SimpleSerializer = SimpleSerializerDebug
else:
    SimpleSerializer = SimpleDiagnosticsSerializer  # SimpleSerializerRelease
