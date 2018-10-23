from golem.marketplace import Offer
from golem.marketplace.rust import order_providers


def test_order_providers():
    offer0 = Offer(scaled_price=2., reputation=1., quality=(1., 1., 6., 1.))
    offer1 = Offer(scaled_price=3., reputation=5., quality=(1., 3., 1., 4.))
    offer2 = Offer(scaled_price=4., reputation=2., quality=(2., 1., 1., 3.))
    res = order_providers([offer0, offer1, offer2])
    # Actual order is not important, just that it is a permutation
    assert sorted(res) == list(range(3))
