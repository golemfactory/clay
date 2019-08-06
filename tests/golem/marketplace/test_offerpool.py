from unittest import TestCase
import sys

from golem.marketplace import scale_price, Offer, OfferPool


class TestScalePrice(TestCase):
    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


class TestOfferPool(TestCase):
    TASK_A = 'aaa'

    @staticmethod
    def _mock_offer() -> Offer:
        return Offer(
            scaled_price=1.,
            reputation=1.,
            quality=(0., 0., 0., 0.),
        )

    def test_choose_from_empty_pool(self):
        with self.assertRaises(KeyError):
            OfferPool.choose_offers(self.TASK_A)

    def test_empty_after_choice(self):
        offer = self._mock_offer()
        OfferPool.add(self.TASK_A, offer)
        OfferPool.add(self.TASK_A, offer)
        self.assertEqual(
            OfferPool.get_task_offer_count(self.TASK_A), 2)

        _ = OfferPool.choose_offers(self.TASK_A)
        self.assertEqual(
            OfferPool.get_task_offer_count(self.TASK_A),
            0
        )

    def test_resolution_length_correct(self):
        offer = self._mock_offer()
        OfferPool.add(self.TASK_A, offer)
        OfferPool.add(self.TASK_A, offer)
        self.assertEqual(
            OfferPool.get_task_offer_count(self.TASK_A), 2)
        result = OfferPool.choose_offers(self.TASK_A)
        self.assertEqual(len(result), 2)
