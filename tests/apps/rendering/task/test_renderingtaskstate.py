from unittest import TestCase

from golem.testutils import PEP8MixIn


class TestRenderingTaskStateStyle(TestCase, PEP8MixIn):

    PEP8_FILES = [
        "apps/rendering/task/renderingtaskstate.py"
    ]
