from pathlib import Path

from .src.minilight import make_perf_test as make_perf_test_impl

TESTFILE = Path(__file__).parent / 'cornellbox.ml.txt'


def make_perf_test() -> float:
    return make_perf_test_impl(str(TESTFILE))
