import unittest

import faker
import semantic_version

from golem import utils

fake = faker.Faker()


class GetVersionSpecTest(unittest.TestCase):
    def test_basic(self):
        v = semantic_version.Version('0.11.0+dev347.gdb685e2')
        spec = utils.get_version_spec(v)
        lower, higher = spec.specs
        self.assertEqual(lower.kind, '>=')
        self.assertEqual(lower.spec, semantic_version.Version('0.11.0'))
        self.assertEqual(higher.kind, '<')
        self.assertEqual(higher.spec, semantic_version.Version('0.12.0'))


class IsVersionCompatibleTest(unittest.TestCase):
    def setUp(self):
        self.version = semantic_version.Version('0.11.1+dev347.gdb685e2')
        self.spec = utils.get_version_spec(self.version)

    def test_higher_minor(self):
        self.assertFalse(utils.is_version_compatible('0.12.0', self.spec))

    def test_higher_patch(self):
        self.assertTrue(utils.is_version_compatible('0.11.2', self.spec))

    def test_equal(self):
        self.assertTrue(
            utils.is_version_compatible(str(self.version), self.spec),
        )

    def test_lower_patch(self):
        self.assertTrue(utils.is_version_compatible('0.11.0', self.spec))

    def test_lower_minor(self):
        self.assertFalse(utils.is_version_compatible('0.10.1', self.spec))

    def test_None(self):
        self.assertFalse(utils.is_version_compatible(None, self.spec))

    def test_invalid(self):
        self.assertFalse(utils.is_version_compatible(fake.word(), self.spec))  # noqa pylint: disable=no-member
