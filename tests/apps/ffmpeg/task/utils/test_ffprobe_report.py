import copy
import os
from typing import Any, List
from unittest import TestCase, mock

import pytest
from parameterized import parameterized

from apps.transcoding.ffmpeg.task import ffmpegTaskTypeInfo
from golem.tools.ci import ci_skip
from golem.docker.manager import DockerManager
from golem.docker.task_thread import DockerTaskThread
from golem.testutils import TempDirFixture
from tests.apps.ffmpeg.task.utils.ffprobe_report import FfprobeFormatReport, \
    FuzzyDuration, FuzzyInt, FfprobeAudioAndVideoStreamReport, \
    FfprobeVideoStreamReport, FfprobeAudioStreamReport, FfprobeStreamReport, \
    DiffReason
from tests.apps.ffmpeg.task.utils.ffprobe_report_sample_reports import \
    RAW_REPORT_ORIGINAL, RAW_REPORT_WITH_MPEG4


class WrongRawReportFormatException(TypeError):
    pass


class TestFfprobeFormatReport(TestCase):
    def setUp(self):
        super().setUp()

        # We'll be comparing output from FfprobeFormatReport.diff() which
        # can be long but we still want to see it all.
        self.maxDiff = None

    @staticmethod
    def _change_value_in_dict(dict_path: List[tuple],
                              new_value: Any,
                              raw_report_to_modify: dict) -> dict:

        for fields in dict_path:
            sub_dict = raw_report_to_modify
            for field in fields:
                if field == fields[-1]:
                    sub_dict[field] = new_value
                else:
                    if isinstance(sub_dict, dict):
                        sub_dict = sub_dict.get(field)  # type: ignore
                    elif isinstance(sub_dict, list):
                        sub_dict = sub_dict[field]
                    else:
                        raise WrongRawReportFormatException(
                            f'Raw report should contain only nested lists '
                            f'or dictionaries, not {type(sub_dict)}'
                        )
        return raw_report_to_modify

    def test_reports_with_shuffled_streams_should_be_compared_as_equal(self):
        report_original = FfprobeFormatReport(RAW_REPORT_ORIGINAL)
        raw_report_shuffled = copy.deepcopy(RAW_REPORT_ORIGINAL)

        for stream in raw_report_shuffled['streams']:
            if stream['index'] % 2 == 0:
                stream['index'] = stream['index'] + 1
            else:
                stream['index'] = stream['index'] - 1

        sorted(raw_report_shuffled['streams'], key=lambda i: i['index'])
        assert raw_report_shuffled != RAW_REPORT_ORIGINAL
        report_shuffled = FfprobeFormatReport(raw_report_shuffled)

        self.assertEqual(report_original, report_shuffled)

    def test_missing_expected_stream_should_be_reported(self):
        raw_report_original = copy.deepcopy(RAW_REPORT_ORIGINAL)
        del raw_report_original['streams'][2]
        report_original = FfprobeFormatReport(raw_report_original)

        raw_report_expected = copy.deepcopy(RAW_REPORT_ORIGINAL)
        del raw_report_expected['streams'][10]
        del raw_report_expected['streams'][9]
        report_expected = FfprobeFormatReport(raw_report_expected)

        diff = report_expected.diff(report_original)

        expected_diff = [
            {
                'location': 'format',
                'attribute': 'stream_types',
                'actual_value':
                    {
                        'video': 1,
                        'audio': 2,
                        'subtitle': 6
                    },
                'expected_value':
                    {
                        'video': 1,
                        'audio': 2,
                        'subtitle': 7
                    },
                'reason': DiffReason.DifferentAttributeValues.value,
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'eng',
                'expected_value': 'hun',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 2,
                'expected_stream_index': 3
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'hun',
                'expected_value': 'ger',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 3,
                'expected_stream_index': 4
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'ger',
                'expected_value': 'fre',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 4,
                'expected_stream_index': 5
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'fre',
                'expected_value': 'spa',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 5,
                'expected_stream_index': 6
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'spa',
                'expected_value': 'ita',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 6,
                'expected_stream_index': 7
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'ita',
                'expected_value': 'jpn',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 7,
                'expected_stream_index': 9
            },
            {
                'location': 'subtitle',
                'actual_stream_index': None,
                'expected_stream_index': 10,
                'reason': DiffReason.NoMatchingStream.value}
        ]
        self.assertCountEqual(diff, expected_diff)

    def test_missing_actual_stream_should_be_reported(self):
        raw_report_original = copy.deepcopy(RAW_REPORT_ORIGINAL)
        del raw_report_original['streams'][10]
        del raw_report_original['streams'][9]
        report_original = FfprobeFormatReport(raw_report_original)

        raw_report_expected = copy.deepcopy(RAW_REPORT_ORIGINAL)
        del raw_report_expected['streams'][2]
        report_expected = FfprobeFormatReport(raw_report_expected)

        diff = (report_expected.diff(report_original))
        expected_diff = [
            {
                'location': 'format',
                'attribute': 'stream_types',
                'actual_value': {
                    'audio': 2,
                    'video': 1,
                    'subtitle': 7
                },
                'expected_value': {
                    'video': 1,
                    'audio': 2,
                    'subtitle': 6,
                },
                'reason': DiffReason.DifferentAttributeValues.value,
            },
            {
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'jpn',
                'expected_value': 'eng',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 9,
                'expected_stream_index': 2,

            },
            {
                'location': 'subtitle',
                'actual_stream_index': 6,
                'expected_stream_index': None,
                'reason': DiffReason.NoMatchingStream.value,
            },
        ]
        self.assertCountEqual(diff, expected_diff)

    def test_report_should_have_video_fields_with_proper_values(self):
        raw_report = copy.deepcopy(RAW_REPORT_WITH_MPEG4)
        raw_report['streams'][0]['width'] = 560
        raw_report['streams'][0]['height'] = 320
        raw_report['streams'][0]['pix_fmt'] = 'yuv420p'
        raw_report['streams'][0]['r_frame_rate'] = '30/1'

        report = FfprobeFormatReport(raw_report)

        self.assertEqual(report.stream_reports[0].resolution, [560, 320])
        self.assertEqual(report.stream_reports[0].pixel_format, 'yuv420p')
        self.assertEqual(report.stream_reports[0].frame_rate, 30)

    def test_all_video_properties_are_tested(self):
        video_attributes = [
            x
            for x in FfprobeVideoStreamReport.ATTRIBUTES_TO_COMPARE
            if x not in FfprobeAudioAndVideoStreamReport.ATTRIBUTES_TO_COMPARE
        ]
        self.assertCountEqual(
            video_attributes,
            ['resolution', 'pixel_format', 'frame_rate']
        )

    def test_report_should_have_audio_fields_with_proper_values(self):
        raw_report = copy.deepcopy(RAW_REPORT_WITH_MPEG4)
        raw_report['streams'][1]['sample_rate'] = '48000'
        raw_report['streams'][1]['channels'] = 1
        raw_report['streams'][1]['channel_layout'] = 'mono'
        if hasattr(raw_report['streams'][1], 'sample_format'):
            del raw_report['streams'][1]['sample_format']

        report = FfprobeFormatReport(RAW_REPORT_WITH_MPEG4)

        self.assertEqual(report.stream_reports[1].sample_rate, 48000)
        self.assertEqual(report.stream_reports[1].sample_format, None)
        self.assertEqual(report.stream_reports[1].channel_count, 1)
        self.assertEqual(report.stream_reports[1].channel_layout, 'mono')

    def test_all_audio_properties_are_tested(self):
        audio_attributes = [
            x
            for x in FfprobeAudioStreamReport.ATTRIBUTES_TO_COMPARE
            if x not in FfprobeAudioAndVideoStreamReport.ATTRIBUTES_TO_COMPARE
        ]
        self.assertCountEqual(
            audio_attributes,
            ['sample_rate', 'sample_format', 'channel_count', 'channel_layout']
        )

    def test_report_should_have_audio_and_video_fields_with_proper_values(self):
        raw_report = copy.deepcopy(RAW_REPORT_WITH_MPEG4)
        raw_report['streams'][0]['duration'] = '5.566667'
        raw_report['streams'][0]['bit_rate'] = '499524'
        raw_report['streams'][0]['nb_frames'] = '167'

        raw_report['streams'][1]['duration'] = '5.640000'
        raw_report['streams'][1]['bit_rate'] = '64275'
        raw_report['streams'][1]['nb_frames'] = '235'

        report = FfprobeFormatReport(RAW_REPORT_WITH_MPEG4)

        self.assertEqual(report.stream_reports[0].duration.duration, 5.566667)
        self.assertEqual(report.stream_reports[0].bitrate.value, 499524)
        self.assertEqual(report.stream_reports[0].frame_count, 167)

        self.assertEqual(report.stream_reports[1].duration.duration, 5.64)
        self.assertEqual(report.stream_reports[1].bitrate.value, 64275)
        self.assertEqual(report.stream_reports[1].frame_count, 235)

    def test_all_audio_and_video_properties_are_tested(self):
        audio_and_video_attributes = [
            x
            for x in FfprobeAudioAndVideoStreamReport.ATTRIBUTES_TO_COMPARE
            if x not in FfprobeStreamReport.ATTRIBUTES_TO_COMPARE
        ]
        self.assertCountEqual(
            audio_and_video_attributes,
            ['duration', 'bitrate', 'frame_count']
        )

    def test_report_should_have_stream_fields_with_proper_values(self):
        raw_report = copy.deepcopy(RAW_REPORT_WITH_MPEG4)
        raw_report['streams'][0]['codec_type'] = 'video'
        raw_report['streams'][0]['codec_name'] = 'mpeg4'
        raw_report['streams'][0]['start_time'] = '0.000000'

        raw_report['streams'][1]['codec_type'] = 'audio'
        raw_report['streams'][1]['codec_name'] = 'mp3'
        raw_report['streams'][1]['start_time'] = '0.000000'

        report = FfprobeFormatReport(RAW_REPORT_WITH_MPEG4)

        self.assertEqual(report.stream_reports[0].codec_type, 'video')
        self.assertEqual(report.stream_reports[0].codec_name, 'mpeg4')
        self.assertEqual(report.stream_reports[0].start_time.duration, 0)

        self.assertEqual(report.stream_reports[1].codec_type, 'audio')
        self.assertEqual(report.stream_reports[1].codec_name, 'mp3')
        self.assertEqual(report.stream_reports[1].start_time.duration, 0)

    def test_all_stream_properties_are_tested(self):
        self.assertCountEqual(
            FfprobeStreamReport.ATTRIBUTES_TO_COMPARE,
            ['codec_type', 'codec_name', 'start_time']
        )

    def test_report_should_have_format_fields_with_proper_values(self):
        raw_report = copy.deepcopy(RAW_REPORT_WITH_MPEG4)
        raw_report['streams'][0]['codec_type'] = 'video'
        raw_report['streams'][1]['codec_type'] = 'audio'
        assert len(RAW_REPORT_WITH_MPEG4['streams']) == 2
        raw_report['format']['format_name'] = 'avi'
        raw_report['format']['duration'] = '5.640000'
        raw_report['format']['start_time'] = '0.000000'
        raw_report['format']['nb_programs'] = 0

        report = FfprobeFormatReport(RAW_REPORT_WITH_MPEG4)

        self.assertEqual(report.stream_types, {'audio': 1, 'video': 1})
        self.assertEqual(report.format_name, 'avi')
        self.assertEqual(report.duration.duration, 5.64)
        self.assertEqual(report.start_time.duration, 0)
        self.assertEqual(report.program_count, 0)

    def test_all_format_properties_are_tested(self):
        self.assertCountEqual(
            FfprobeFormatReport.ATTRIBUTES_TO_COMPARE,
            [
                'format_name', 'stream_types', 'duration', 'start_time',
                'program_count'
            ]
        )

    def test_diff_equal_to_expected(self):
        report_original = FfprobeFormatReport(RAW_REPORT_ORIGINAL)
        raw_report_expected = copy.deepcopy(RAW_REPORT_ORIGINAL)
        raw_report_expected['format']['start_time'] = 10
        report_expected = FfprobeFormatReport(raw_report_expected)

        diff = (report_expected.diff(report_original))
        expected_diff = [{'location': 'format', 'attribute': 'start_time',
                          'actual_value': FuzzyDuration(10, 0),
                          'expected_value': FuzzyDuration(0.0, 0),
                          'reason': DiffReason.DifferentAttributeValues.value}]

        self.assertCountEqual(diff, expected_diff)

    @parameterized.expand([
        (
            [('format', 'start_time')],
            10,
            [{
                'location': 'format',
                'attribute': 'start_time',
                'actual_value': FuzzyDuration(10.0, 0),
                'expected_value': FuzzyDuration(0.0, 0),
                'reason': DiffReason.DifferentAttributeValues.value,
            }],
        ),
        (
            [('format', 'duration')],
            80,
            [{
                'location': 'format',
                'attribute': 'duration',
                'actual_value': FuzzyDuration(80, 10),
                'expected_value': FuzzyDuration(46.665, 10),
                'reason': DiffReason.DifferentAttributeValues.value,
            }],
        ),
        (
            [('format', 'nb_programs')],
            2,
            [{
                'location': 'format',
                'attribute': 'program_count',
                'actual_value': 2,
                'expected_value': 0,
                'reason': DiffReason.DifferentAttributeValues.value,
            }],
        ),
        (
            [('streams', 0, 'codec_name')],
            'flv',
            [{
                'location': 'video',
                'attribute': 'codec_name',
                'actual_value': 'flv',
                'expected_value': 'h264',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 0,
                'expected_stream_index': 0,
            }],
        ),
        (
            [('streams', 1, 'start_time')],
            '0.5',
            [{
                'location': 'audio',
                'attribute': 'start_time',
                'actual_value': FuzzyDuration(0.5, 0.05),
                'expected_value': FuzzyDuration(0.012, 0.05),
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 1,
                'expected_stream_index': 1,
            }],
        ),
        (
            [('streams', 1, 'duration')],
            '0.5',
            [{
                'location': 'audio',
                'attribute': 'duration',
                'actual_value': FuzzyDuration(0.5, 0.05),
                'expected_value': None,
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 1,
                'expected_stream_index': 1,
            }],
        ),
        (
            [('streams', 0, 'width')],
            1920,
            [{
                'location': 'video',
                'attribute': 'resolution',
                'actual_value': [1920, 576],
                'expected_value': [1024, 576],
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 0,
                'expected_stream_index': 0,
            }],
        ),
        (
            [('streams', 0, 'resolution')],
            [1920, 1080],
            [{
                'location': 'video',
                'attribute': 'resolution',
                'actual_value': [[1920, 1080], 1024, 576],
                'expected_value': [1024, 576],
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 0,
                'expected_stream_index': 0,
            }],
        ),
        (
            [('streams', 0, 'resolution')],
            [1024, 576],
            [],
        ),

        (
            [('streams', 0, 'r_frame_rate')],
            '12/1',
            [{
                'location': 'video',
                'attribute': 'frame_rate',
                'actual_value': 12,
                'expected_value': 24,
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 0,
                'expected_stream_index': 0,
            }],
        ),
        (
            [('streams', 1, 'sample_rate')],
            '24000',
            [{
                'location': 'audio',
                'attribute': 'sample_rate',
                'actual_value': 24000,
                'expected_value': 48000,
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 1,
                'expected_stream_index': 1,
            }],
        ),
        (
            [('streams', 4, 'tags', 'language')],
            'eng',
            [{
                'location': 'subtitle',
                'attribute': 'language',
                'actual_value': 'eng',
                'expected_value': 'ger',
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 4,
                'expected_stream_index': 4,
            }],
        ),
        (
            [('streams', 1, 'bit_rate')],
            '499524',
            [{
                'location': 'audio',
                'attribute': 'bitrate',
                'actual_value': FuzzyInt(499524, 5),
                'expected_value': None,
                'reason': DiffReason.DifferentAttributeValues.value,
                'actual_stream_index': 1,
                'expected_stream_index': 1,
            }],
        ),
    ])
    def test_that_changed_raw_report_field_is_reported_in_diff(
            self,
            dict_path,
            new_value,
            expected_diff,
    ):
        report_original = FfprobeFormatReport(RAW_REPORT_ORIGINAL)
        raw_report_expected = copy.deepcopy(RAW_REPORT_ORIGINAL)
        raw_report_expected = self._change_value_in_dict(
            dict_path,
            new_value,
            raw_report_expected,
        )
        assert raw_report_expected != RAW_REPORT_ORIGINAL
        report_expected = FfprobeFormatReport(raw_report_expected)

        diff = report_expected.diff(report_original)
        self.assertCountEqual(diff, expected_diff)

    @parameterized.expand([
        (
            [('format', 'start_time')],
            10,
            {'format': {'start_time': 0}},
        ),
        (
            [('format', 'duration')],
            80,
            {'format': {'duration': 46.665}},
        ),
        (
            [('format', 'nb_programs')],
            2,
            {'format': {'program_count': 0}},
        ),
        (
            [('streams', 0, 'codec_name')],
            'h265',
            {'video': {'codec_name': 'h264'}},
        ),
        (
            [
                ('streams', 1, 'codec_name'),
                ('streams', 8, 'codec_name'),
            ],
            'xx',
            {'audio': {'codec_name': 'aac'}},
        ),
    ])
    def test_that_override_in_diff_should_work_correctly(
            self,
            dict_path,
            new_value,
            overrides,
    ):
        report_original = FfprobeFormatReport(RAW_REPORT_ORIGINAL)
        raw_report_expected = copy.deepcopy(RAW_REPORT_ORIGINAL)
        raw_report_expected = self._change_value_in_dict(
            dict_path,
            new_value,
            raw_report_expected
        )
        assert raw_report_expected != RAW_REPORT_ORIGINAL

        report_expected = FfprobeFormatReport(raw_report_expected)
        diff = (report_original.diff(
            expected_report=report_expected,
            overrides=overrides,
        ))
        self.assertCountEqual(diff, [])

    @parameterized.expand([
        (
            [('format', 'start_time')],
            100,
            {'format': {'start_time'}},
        ),
        (
            [('format', 'duration')],
            80,
            {'format': {'duration'}},
        ),
        (
            [('format', 'nb_programs')],
            2,
            {'format': {'program_count'}},
        ),
        (
            [('streams', 0, 'codec_name')],
            'flv',
            {'video': {'codec_name'}},
        ),
        (
            [
                ('streams', 1, 'codec_name'),
                ('streams', 8, 'codec_name'),
            ],
            'xx',
            {'audio': {'codec_name': 'aac'}},
        ),
    ])
    def test_that_exclude_in_diff_should_work_correctly(
            self,
            fields_to_change,
            new_value,
            excludes,
    ):

        report_original = FfprobeFormatReport(RAW_REPORT_ORIGINAL)
        raw_report_expected = copy.deepcopy(RAW_REPORT_ORIGINAL)
        raw_report_expected = self._change_value_in_dict(
            fields_to_change,
            new_value,
            raw_report_expected,
        )
        assert raw_report_expected != RAW_REPORT_ORIGINAL

        report_expected = FfprobeFormatReport(raw_report_expected)
        diff = (report_original.diff(
            expected_report=report_expected,
            excludes=excludes,
        ))
        self.assertCountEqual(diff, [])


class TestFuzzyDuration(TestCase):
    @parameterized.expand([
        (100.0, 0, 100, 0),
        (80, 10.0, 100, 10),
        (10, 20, -20, 20),
        (110, 0, 100, 10),
    ])
    def test_that_fuzzy_durations_should_be_equal_if_such_parameters_given(
            self,
            duration_1,
            tolerance_1,
            duration_2,
            tolerance_2,
    ):
        self.assertEqual(
            FuzzyDuration(duration_1, tolerance_1),
            FuzzyDuration(duration_2, tolerance_2)
        )

    @parameterized.expand([
        (100.0, 0, 99.9, 0),
        (80, 9.9, 100, 10),
        (10, 10, -20, 10),
        (100, 0, 120, 10),
    ])
    def test_that_fuzzy_durations_should_not_be_equal_if_such_parameters_given(
            self,
            duration_1,
            tolerance_1,
            duration_2,
            tolerance_2,
    ):
        self.assertNotEqual(
            FuzzyDuration(duration_1, tolerance_1),
            FuzzyDuration(duration_2, tolerance_2)
        )


class TestFuzzyInt(TestCase):
    @parameterized.expand([
        (100, 0, 100, 0),
        (80, 10, 88, 0),
        (60, 0, 100, 40),
        (120, 10, 100, 10),
    ])
    def test_that_fuzzy_int_should_be_equal_if_such_parameters_given(
            self,
            value_1,
            tolerance_percent_1,
            value_2,
            tolerance_percent_2,
    ):
        self.assertEqual(
            FuzzyInt(value_1, tolerance_percent_1),
            FuzzyInt(value_2, tolerance_percent_2)
        )

    @parameterized.expand([
        (101, 0, 100, 0),
        (80, 10, 100, 10),
        (60, 40, 100, 0),
        (100, 2, 120, 10),
    ])
    def test_that_fuzzy_int_should_not_be_equal_if_such_parameters_given(
            self,
            value_1,
            tolerance_percent_1,
            value_2,
            tolerance_percent_2,
    ):
        self.assertNotEqual(
            FuzzyInt(value_1, tolerance_percent_1),
            FuzzyInt(value_2, tolerance_percent_2)
        )


@ci_skip
class TestFfprobeReportBuild(TempDirFixture):
    def setUp(self):
        super().setUp()

        self.tt = ffmpegTaskTypeInfo()
        dm = DockerTaskThread.docker_manager = DockerManager.install()
        dm.update_config(
            status_callback=mock.Mock(),
            done_callback=mock.Mock(),
            work_dir=self.new_path,
            in_background=True)
        self.resources_dir = self.RESOURCES = os.path.join(os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
            'resources')

    @pytest.mark.slow
    def test_build_should_return_list_with_one_ffprobe_format_report_instance(
            self):
        reports = FfprobeFormatReport.build(
            tmp_dir='/tmp/',
            video_paths=[os.path.join(self.resources_dir, 'test_video.mp4')]
        )
        self.assertIsInstance(reports, List)
        self.assertEqual(len(reports), 1)
        self.assertIsInstance(reports[0], FfprobeFormatReport)
