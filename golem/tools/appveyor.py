import os
import unittest


def appveyor_skip(reason='Appveyor environment'):
    print os.environ.get('APPVEYOR', False)
    if os.environ.get('APPVEYOR', False):
        return unittest.skip(reason)
    return _id


def _id(obj):
    return obj
