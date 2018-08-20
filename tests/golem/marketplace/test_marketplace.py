from golem.marketplace import pick_provider


def test_pick_provider():
    assert pick_provider([2.0, 1.8, 3.0, 4.4]) == 1
