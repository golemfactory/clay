import pathlib
from unittest.mock import patch

from faker import Faker

from golem.model import GenericKeyValue
from golem import terms
from golem.tools.testwithdatabase import TestWithDatabase


fake = Faker()


class TestTermsOfUseBase(TestWithDatabase):
    def setUp(self):
        super().setUp()

        class TestTermsOfUse(terms.TermsOfUseBase):
            ACCEPTED_KEY = fake.sentence()
            VERSION = fake.pyint()
            PATH = pathlib.Path("NOT_USED")

        self.terms = TestTermsOfUse

    def test_are_accepted_no_entry(self):
        self.assertFalse(self.terms.are_accepted())

    def test_are_accepted_old_version(self):
        GenericKeyValue.create(
            key=self.terms.ACCEPTED_KEY,
            value=self.terms.VERSION - 1)
        self.assertFalse(self.terms.are_accepted())

    def test_are_accepted_right_version(self):
        GenericKeyValue.create(
            key=self.terms.ACCEPTED_KEY,
            value=self.terms.VERSION)
        self.assertTrue(self.terms.are_accepted())

    def test_accept_of_use_no_entry(self):
        self.terms.accept()
        self.assertTrue(self.terms.are_accepted())

    def test_accept_of_use_old_version(self):
        GenericKeyValue.create(
            key=self.terms.ACCEPTED_KEY,
            value=self.terms.VERSION - 1)
        self.terms.accept()
        self.assertTrue(self.terms.are_accepted())

    def test_accept_right_version(self):
        GenericKeyValue.create(
            key=self.terms.ACCEPTED_KEY,
            value=self.terms.VERSION)
        self.terms.accept()
        self.assertTrue(self.terms.are_accepted())

    @patch("pathlib.Path.read_text")
    def test_show(self, read_mock):
        content = """
        GOLEM TERMS OF USE
        ==================
        Bla bla bla bla
        """
        read_mock.return_value = content
        self.assertEqual(self.terms.show(), content)
