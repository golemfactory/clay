# pylint: disable=protected-access
import unittest
from unittest import mock


from golem.interface.client import concent


class TestTerms(unittest.TestCase):
    def setUp(self):
        self.client = concent.Concent.client = mock.MagicMock()
        self.terms = concent.Terms()

    def tearDown(self):
        del concent.Concent.client

    def test_show(self):
        self.terms.show()
        self.client._call.assert_called_once_with("golem.concent.terms.show")

    def test_accept(self):
        self.terms.accept()
        self.client._call.assert_called_once_with("golem.concent.terms.accept")
