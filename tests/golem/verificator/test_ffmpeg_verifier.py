from os import remove
from os.path import isfile

from pytest import fixture, raises

from golem.verificator.ffmpeg_verifier import FFmpegVerifier

TEST_FILE = "output.m3u8"


@fixture
def result_file():
    with open(TEST_FILE, "a") as file:
        file.write("")
    yield TEST_FILE
    remove(TEST_FILE)
    assert isfile(TEST_FILE) is False


@fixture
def results(result_file):
    return [result_file]


@fixture
def verification_data(results):
    return {
        "results": results
    }


@fixture
def empty_verifier():
    return FFmpegVerifier(verification_data=dict())


@fixture
def verifier(verification_data):
    return FFmpegVerifier(verification_data=verification_data)


# pylint: disable=protected-access

def test_verifier_get_result_info_without_key(empty_verifier):
    with raises(KeyError):
        empty_verifier._get_result_info(dict())


def test_verifier_get_result_info(verifier, verification_data, results):
    assert verifier._get_result_info(verification_data) == results


def test_check_file_existence_no_file(empty_verifier):
    with raises(FileNotFoundError):
        empty_verifier._check_file_existence(TEST_FILE)


def test_check_file_existence(verifier, result_file):
    assert verifier._check_file_existence(result_file)


def test_check_results_no_results(empty_verifier):
    with raises(RuntimeError):
        empty_verifier._check_results(list())


def test_check_file_existence_result_does_not_exist(empty_verifier):
    with raises(FileNotFoundError):
        empty_verifier._check_results([TEST_FILE])


def test_check_results(verifier, results):
    assert verifier._check_results(results)


def test_simple_verification_no_verification_data(empty_verifier):
    assert empty_verifier.simple_verification(dict()) is False


def test_simple_verification_no_results(empty_verifier):
    assert empty_verifier.simple_verification({"results": []}) is False


def test_simple_verification_no_verification_result_file_does_not_exist(empty_verifier):
    assert empty_verifier.simple_verification({"results": [TEST_FILE]}) is False


def test_simple_verification(verifier, verification_data):
    assert verifier.simple_verification(verification_data)
    assert verifier.results == [TEST_FILE]
