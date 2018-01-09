from unittest import TestCase
from semantic_version import Version

import golem

class TestVariables(TestCase):

    def test_app_version(self):
        v = golem.__version__.split('.')
        assert len(v) >= 3
        assert '.'.join(v) == golem.__version__
        # semantic_version shouldn't throw
        Version(golem.__version__)
