from golem.marketplace import order_providers


def test_order_providers():
    assert order_providers([2.0, 1.8, 5.0, 4.4]) == [1, 0, 3, 2]
