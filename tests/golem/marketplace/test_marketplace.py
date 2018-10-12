from golem.marketplace import order_providers


def test_order_providers():
    assert order_providers([2.0, 1.8, 3.0, 4.4]) == [0, 1, 2, 3]
