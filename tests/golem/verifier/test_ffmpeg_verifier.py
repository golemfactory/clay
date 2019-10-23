from os import remove
from os.path import isfile

from pytest import fixture, raises
from golem.verifier.core_verifier import SubtaskVerificationState
from golem.verifier.ffmpeg_verifier import FFmpegVerifier

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
        "results": results,
        "subtask_info": {}
    }


@fixture
def empty_results():
    return {
        "results": [],
        "subtask_info": {}
    }


@fixture
def verifier():
    def _verifier(data):
        return FFmpegVerifier(data)

    return _verifier


def test_simple_verification_no_results(verifier, empty_results):
    ffmpeg_verifier = verifier(empty_results)
    assert ffmpeg_verifier.simple_verification() is False
    assert ffmpeg_verifier.state == SubtaskVerificationState.WRONG_ANSWER


def test_simple_verification_no_verification_result_file_does_not_exist(
        verifier, empty_results):

    ffmpeg_verifier = verifier(empty_results)
    assert ffmpeg_verifier.simple_verification() is False
    assert ffmpeg_verifier.state == SubtaskVerificationState.WRONG_ANSWER


def test_simple_verification(verifier, verification_data):
    ffmpeg_verifier = verifier(verification_data)
    assert ffmpeg_verifier.simple_verification()
    assert ffmpeg_verifier.results == [TEST_FILE]
    assert ffmpeg_verifier.state == SubtaskVerificationState.VERIFIED
