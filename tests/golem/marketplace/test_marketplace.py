from golem.marketplace import order_providers, Offer


def test_order_providers():
    offer0 = Offer(scaled_price=2.0)
    offer1 = Offer(scaled_price=1.8)
    offer2 = Offer(scaled_price=4.4)
    res = order_providers([offer0, offer1, offer2])
    # Actual order is not important, just that it is a permutation
    assert sorted(res) == list(range(3))
