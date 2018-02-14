import pathlib
import unittest

from golem import testutils
from golem.core import common

GOLEM_PATH = pathlib.Path(common.get_golem_path())
CONCENT_PATH = GOLEM_PATH / "golem/network/concent"


class ConformanceTestCase(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        p.relative_to(GOLEM_PATH) for p in CONCENT_PATH.glob('**/*.py')
        if p.is_file()
    ]
