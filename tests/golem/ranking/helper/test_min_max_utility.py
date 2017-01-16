from unittest import TestCase

from golem.ranking.helper.min_max_utility import POS_WEIGHT, NEG_WEIGHT, MIN_OPERATION_NUMBER, count_trust, vec_to_trust
from golem.ranking.helper.trust_const import MIN_TRUST, MAX_TRUST


class TestMinMaxUtility(TestCase):
    def test_should_count_trust(self):
        """Should calculate trust for various combinations of pos and neg using formula
        min(MAX_TRUST, max(MIN_TRUST, (pos * POS_WEIGHT - neg * NEG_WEIGHT) / max(pos + neg, MIN_OPERATION_NUMBER)))."""
        pos = -1.3
        neg = 1.3
        self.assertEqual(count_trust(pos, neg), min(MAX_TRUST, max(MIN_TRUST, (pos * POS_WEIGHT - neg * NEG_WEIGHT)
                                                                   / max(pos + neg, MIN_OPERATION_NUMBER))))
        pos = 5.0
        neg = 1.3
        self.assertEqual(count_trust(pos, neg), min(MAX_TRUST, max(MIN_TRUST, (pos * POS_WEIGHT - neg * NEG_WEIGHT)
                                                                   / max(pos + neg, MIN_OPERATION_NUMBER))))
        self.assertAlmostEqual(count_trust(pos, neg), 0.048, 7)

        self.assertAlmostEqual(-0.052, count_trust(0.0, 1.3), 7)
        self.assertAlmostEqual(0.026, count_trust(1.3, 0.0), 7)
        self.assertAlmostEqual(-0.204, count_trust(0.0, 5.1), 7)
        self.assertAlmostEqual(0.102, count_trust(5.1, 0.0), 7)

    def test_should_count_trust_throw_exception(self):
        """Should throw exception for non float parameter values."""
        with self.assertRaises(TypeError):
            count_trust("alpha", 0.5)
            count_trust("alpha", "beta")

    def test_should_convert_vec_to_trust(self):
        """Should convert two dimensional vector (a,b) to trust_value specified by formula:
            min(MAX_TRUST, max(MIN_TRUST, float(a) / float(b)))
        """
        vec = None
        self.assertEqual(0.0, vec_to_trust(vec))

        vec = 5.0, 1.3
        a, b = vec
        self.assertEqual(min(MAX_TRUST, max(MIN_TRUST, float(a) / float(b))), vec_to_trust(vec))
        self.assertEqual(1.0, vec_to_trust(vec))

        vec = 0.0, 1.3
        self.assertEqual(0.0, vec_to_trust(vec))

        vec = 5.0, 0.0
        self.assertEqual(0.0, vec_to_trust(vec))

        vec = 0.0, 0.0
        self.assertEqual(0.0, vec_to_trust(vec))

    def test_should_vec_to_trust_throw_exception(self):
        """Should throw exception for non float parameter values."""
        vec = "beta", "alpha"
        self.assertEqual(None, vec_to_trust(vec))

        vec = 5.0, "alpha"
        self.assertEqual(None, vec_to_trust(vec))

        vec = "alpha", 1.3
        self.assertEqual(None, vec_to_trust(vec))
