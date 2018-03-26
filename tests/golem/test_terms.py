import os
from unittest.mock import patch

from golem.model import GenericKeyValue
from golem.terms import TermsOfUse
from golem.tools.testwithdatabase import TestWithDatabase


class TestTermsOfUse(TestWithDatabase):

    def test_are_terms_accepted_no_entry(self):
        self.assertFalse(TermsOfUse.are_terms_accepted())

    def test_are_terms_accepted_old_version(self):
        GenericKeyValue.create(
            key=TermsOfUse.TERMS_ACCEPTED_KEY,
            value=TermsOfUse.TERMS_VERSION - 1)
        self.assertFalse(TermsOfUse.are_terms_accepted())

    def test_are_terms_accepted_right_version(self):
        GenericKeyValue.create(
            key=TermsOfUse.TERMS_ACCEPTED_KEY,
            value=TermsOfUse.TERMS_VERSION)
        self.assertTrue(TermsOfUse.are_terms_accepted())

    def test_accept_terms_of_use_no_entry(self):
        TermsOfUse.accept_terms()
        self.assertTrue(TermsOfUse.are_terms_accepted())

    def test_accept_terms_of_use_old_version(self):
        GenericKeyValue.create(
            key=TermsOfUse.TERMS_ACCEPTED_KEY,
            value=TermsOfUse.TERMS_VERSION - 1)
        TermsOfUse.accept_terms()
        self.assertTrue(TermsOfUse.are_terms_accepted())

    def test_accept_terms_right_version(self):
        GenericKeyValue.create(
            key=TermsOfUse.TERMS_ACCEPTED_KEY,
            value=TermsOfUse.TERMS_VERSION)
        TermsOfUse.accept_terms()
        self.assertTrue(TermsOfUse.are_terms_accepted())

    @patch('golem.terms.get_golem_path')
    def test_show_terms(self, get_golem_path):
        get_golem_path.return_value = self.tempdir
        content = """
        GOLEM TERMS OF USE
        ==================
        Bla bla bla bla
        """
        terms_path = self.new_path / TermsOfUse.TERMS_PATH
        os.makedirs(terms_path.parent, exist_ok=True)
        with open(terms_path, mode='w') as terms:
            terms.write(content)

        self.assertEqual(TermsOfUse.show_terms(), content)
