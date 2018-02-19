import pytest

from golem.core.keysauth import KeysAuth


def key_gen(d: int):
    return KeysAuth._generate_keys(difficulty=d)


@pytest.mark.parametrize("d", [10, 11, 12, 13, 14])
def test_key_gen_speed(benchmark, d):
    result = benchmark(key_gen, d)

    # assert KeysAuth.is_difficult(result, d)
