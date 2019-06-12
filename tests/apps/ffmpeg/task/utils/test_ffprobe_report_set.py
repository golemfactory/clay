from parameterized import parameterized

from golem.testutils import TestTaskIntegration
from tests.apps.ffmpeg.task.utils.ffprobe_report import FuzzyInt, DiffReason
from tests.apps.ffmpeg.task.utils.ffprobe_report_set import FfprobeReportSet


class TestFfprobeReportSet(TestTaskIntegration):
    DIFFS_AND_RESULTS = [
        (
            [
                {
                    'location': 'video',
                    'attribute': 'bitrate',
                    'actual_value': FuzzyInt(13795, 5),
                    'expected_value': FuzzyInt(12376, 5),
                    'reason': DiffReason.DifferentAttributeValues.value,
                    'actual_stream_index': 0,
                    'expected_stream_index': 0,
                },
            ],
            {
                'codec change': {
                    'test_video.mp4': {
                        'h264/mp4/2seg': "<ol><li>"
                                         "`video.bitrate`: "
                                         "`12376[+/-5%]` -> "
                                         "`13795[+/-5%]`"
                                         "</li><ol>",
                    },
                },
            },
        ),
        (
            [],
            {
                'codec change': {
                    'test_video.mp4': {'h264/mp4/2seg': 'OK'},
                },
            },
        ),
        (
            [
                {
                    'location': 'format',
                    'attribute': 'stream_types',
                    'actual_value': {
                        'audio': 2,
                        'video': 1,
                        'subtitle': 7,
                    },
                    'expected_value': {
                        'video': 1,
                        'audio': 2,
                        'subtitle': 8,
                    },
                    'reason': DiffReason.DifferentAttributeValues.value,
                },
                {
                    'location': 'subtitle',
                    'actual_stream_index': None,
                    'expected_stream_index': 1,
                    'reason': DiffReason.NoMatchingStream.value,
                },
            ],
            {
                'codec change': {
                    'test_video.mp4': {
                        'h264/mp4/2seg': "<ol><li>"
                                         "`format.stream_types`: `{"
                                         "'video': 1, "
                                         "'audio': 2, "
                                         "'subtitle': 8"
                                         "}` -> `{"
                                         "'audio': 2, "
                                         "'video': 1, "
                                         "'subtitle': 7"
                                         "}`"
                                         "</li><ol>",
                    },
                },
            },
        ),
    ]

    def setUp(self):
        super().setUp()
        self.ffprobe_report_set = FfprobeReportSet()

    @parameterized.expand(DIFFS_AND_RESULTS)
    def test_collect_reports_adds_single_report_table_correctly(
            self,
            diff,
            expected_report_tables,
    ):
        self.ffprobe_report_set.collect_reports(
            diff=diff,
            experiment_name='codec change',
            video_file='test_video.mp4',
            input_value='h264/mp4/2seg',
        )
        self.assertEqual(
            self.ffprobe_report_set._report_tables, expected_report_tables
        )

    @parameterized.expand([
        (
            'custom error message',
            {
                'codec change': {
                    'test_video.mp4': {
                        'h264/mp4/2seg': 'custom error message',
                    },
                },
            },
        ),
        (
            'different error message',
            {
                'codec change': {
                    'test_video.mp4': {
                        'h264/mp4/2seg': 'different error message',
                    },
                },
            },
        ),
    ])
    def test_collect_reports_adds_single_error_table_correctly(
            self,
            error_message,
            expected_error_report_tables,
    ):
        self.ffprobe_report_set.collect_error(
            error_message=error_message,
            experiment_name='codec change',
            video_file='test_video.mp4',
            input_value='h264/mp4/2seg',
        )
        self.assertEqual(
            self.ffprobe_report_set._report_tables,
            expected_error_report_tables,
        )

    def test_collect_reports_collects_multiple_rows_correctly(self):
        expected = {}
        for i in range(3):
            self.ffprobe_report_set.collect_reports(
                diff=self.DIFFS_AND_RESULTS[i][0],
                experiment_name='codec change',
                video_file=f'test_video{i}.mp4',
                input_value='h264/mp4/2seg',
            )
            expected.update({
                f'test_video{i}.mp4': self.DIFFS_AND_RESULTS[i][1][
                    'codec change'][f'test_video.mp4'],
            })
        self.assertDictEqual(
            self.ffprobe_report_set._report_tables['codec change'],
            expected
        )

    def test_collect_reports_collects_report_tables_correctly_in_markdown(self):
        for i in range(3):
            self.ffprobe_report_set.collect_reports(
                diff=self.DIFFS_AND_RESULTS[i][0],
                experiment_name='codec change',
                video_file=f'test_video{i}.mp4',
                input_value='h264/mp4/2seg',
            )
        output = self.ffprobe_report_set.to_markdown()
        # pylint:disable=line-too-long
        self.assertIn('| test_video0.mp4                                    | <ol><li>`video.bitrate`: `12376[+/-5%]` -> `13795[+/-5%]`</li><ol> |', output)
        self.assertIn('| test_video1.mp4                                    | OK                                                 |', output)
        self.assertIn("| test_video2.mp4                                    | <ol><li>`format.stream_types`: `{'video': 1, 'audio': 2, 'subtitle': 8}` -> `{'audio': 2, 'video': 1, 'subtitle': 7}`</li><ol> |", output)
        # pylint:enable=line-too-long
