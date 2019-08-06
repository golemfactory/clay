from unittest import TestCase

import pytest


class TestFails(TestCase):
    @pytest.mark.skip("A test to check teardowns and is skipped by default")
    def test_fails(self):
        self.fail()
