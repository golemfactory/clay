import pathlib
import unittest

from pylint import epylint

from golem import testutils
from golem.core import common

GOLEM_PATH = pathlib.Path(common.get_golem_path())
CONCENT_PATH = GOLEM_PATH / "golem/network/concent"


class ConformanceTestCase(unittest.TestCase, testutils.PEP8MixIn):
    maxDiff = None
    PEP8_FILES = [
        p.relative_to(GOLEM_PATH) for p in CONCENT_PATH.glob('**/*.py')
        if p.is_file()
    ]

    @unittest.skip("Fails on buildbot")
    def test_lint(self):
        base_path = pathlib.Path(common.get_golem_path())
        concent_path = base_path / "golem/network/concent"
        tests_path = base_path / "tests/golem/network/concent"
        options = "{tests_dir} {lib_dir} -f json --rcfile={rcfile}".format(
            rcfile=(base_path / '.pylintrc').as_posix(),
            lib_dir=concent_path.as_posix(),
            tests_dir=tests_path.as_posix(),
        )
        stdout_io, _ = epylint.py_run(options, return_std=True)
        stdout = stdout_io.read()
        self.assertEqual(stdout, '')
