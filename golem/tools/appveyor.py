import os
import unittest

import mock


def in_appveyor():
    return os.environ.get('APPVEYOR', False)


def appveyor_skip(obj):
    if in_appveyor():
        return unittest.skip('Appveyor environment')
    return obj


def appveyor_patch(*args, **kwargs):
    if in_appveyor():
        return mock.patch(*args, **kwargs)
    return _identity


def _identity(obj):
    return obj
