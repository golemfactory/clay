import os
from unittest import mock

from golem.testutils import TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.verificator.blender_verifier import BlenderVerifier, logger


class TestBlenderVerifier(LogTestCase, TempDirFixture):
    pass
