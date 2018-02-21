import pytest

from golem.core.keysauth import KeysAuth


def key_gen(d: int):
    return KeysAuth._generate_keys(difficulty=d)


@pytest.mark.skip
@pytest.mark.parametrize("d", [10, 11, 12, 13, 14, 15, 16])
def test_key_gen_speed(benchmark, d):
    benchmark(key_gen, d)
