from unittest import TestCase
import sys
import pytest

from golem.marketplace import scale_price, Offer, OfferPool


class TestScalePrice(TestCase):
    def test_basic(self):
        assert scale_price(5, 2) == 2.5

    def test_zero(self):
        assert scale_price(5, 0) == sys.float_info.max


class TestOfferPool(TestCase):
    @staticmethod
    def _mock_offer() -> Offer:
        return Offer(
            scaled_price=1.,
            reputation=1.,
            quality=(0., 0., 0., 0.),
        )

    def test_choose_from_empty_pool(self):
        OfferPool.reset()

        with pytest.raises(KeyError):
            OfferPool.choose_offers('aaa')

    def test_all_tasks_empty_after_reset(self):
        OfferPool.reset()

        offer = self._mock_offer()

        OfferPool.add('aaa', offer)
        OfferPool.add('bbb', offer)
        self.assertEqual(
            OfferPool.get_task_offer_count('aaa'), 1)
        self.assertEqual(
            OfferPool.get_task_offer_count('bbb'), 1)

        OfferPool.reset()

        self.assertEqual(
            OfferPool.get_task_offer_count('aaa'), 0)
        self.assertEqual(
            OfferPool.get_task_offer_count('bbb'), 0)

    def test_empty_after_choice(self):
        OfferPool.reset()

        offer = self._mock_offer()
        OfferPool.add('aaa', offer)
        OfferPool.add('aaa', offer)
        self.assertEqual(
            OfferPool.get_task_offer_count('aaa'), 2)

        _ = OfferPool.choose_offers('aaa')
        self.assertEqual(
            OfferPool.get_task_offer_count('aaa'),
            0
        )

    def test_resolution_length_correct(self):
        OfferPool.reset()

        offer = self._mock_offer()
        OfferPool.add('aaa', offer)
        OfferPool.add('aaa', offer)
        self.assertEqual(
            OfferPool.get_task_offer_count('aaa'), 2)
        result = OfferPool.choose_offers('aaa')
        self.assertEqual(len(result), 2)
