import pycodestyle
from pathlib import Path
from golem.core.common import get_golem_path


class Pep8ConformanceTest(object):
    PEP8_FILES = []
    """A mix-in class that adds PEP-8 style conformance.
    To use it in your TestCase just add it to inheritance list like so:
    class MyTestCase(unittest.TestCase, testutils.pep8_conformance_test.Pep8ConformanceTest):
        PEP8_FILES = <iterable>

    PEP8_FILES attribute should be an iterable containing paths of python
    source files relative to <golem root>.

    Afterwards your test case will perform conformance test on files mentioned
    in this attribute.
    """

    def test_conformance(self):
        """Test that we conform to PEP-8."""
        style = pycodestyle.StyleGuide(ignore=[], max_line_length=120)

        # PyCharm needs absolute paths
        base_path = Path(get_golem_path())
        absolute_files = [str(base_path / path) for path in self.PEP8_FILES]

        result = style.check_files(absolute_files)
        self.assertEqual(result.total_errors, 0,
                         "Found code style errors (and warnings).")