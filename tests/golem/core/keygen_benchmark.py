import os
import pytest

from golem.core.keysauth import KeysAuth


def skip_benchmarks():
    return not os.environ.get('benchmarks', False)


def key_gen(d: int):
    return KeysAuth._generate_keys(difficulty=d)


@pytest.mark.skipif(skip_benchmarks(), reason="skip benchmarks by default")
@pytest.mark.parametrize("d", [10, 11, 12, 13, 14])
@pytest.mark.benchmark(min_rounds=20, warmup=False)
def test_key_gen_speed(benchmark, d: int):
    benchmark(key_gen, d)
