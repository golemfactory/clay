from unittest import TestCase
from semantic_version import Version

from golem.core.variables import APP_VERSION

class TestVariables(TestCase):

    def test_app_version(self):
        v = APP_VERSION.split('.')
        assert len(v) == 3
        v = [str(int(i)) for i in v]
        assert '.'.join(v) == APP_VERSION
        # semantic_version shouldn't throw
        Version(APP_VERSION)
