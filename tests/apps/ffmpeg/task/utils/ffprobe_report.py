import json
import os
from enum import Enum
from typing import Any, Collection, Dict, List, Optional, Set, Union

from apps.transcoding.ffmpeg.utils import StreamOperator


DiffDict = Dict[str, Any]
Diff = List[DiffDict]
StreamOverrides = Dict[str, Any]
FileOverrides = Dict[str, StreamOverrides]
StreamExcludes = Set[str]
FileExcludes = Dict[str, Set[str]]


class UnsupportedCodecType(Exception):
    pass


class DiffReason(Enum):
    DifferentAttributeValues = "Different attribute values"
    NoMatchingStream = "No matching stream"


def number_if_possible(value: Any) -> Any:
    if not isinstance(value, (str, bytes)):
        return value

    try:
        return int(value)
    except (ValueError, TypeError):
        pass

    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    return value


def fuzzy_duration_if_possible(value: Any, tolerance: float) -> Any:
    converted_value = number_if_possible(value)

    if isinstance(converted_value, (int, float)):
        return FuzzyDuration(converted_value, tolerance)

    return converted_value


def fuzzy_int_if_possible(value: Any, tolerance_percent: int) -> Any:
    converted_value = number_if_possible(value)

    if isinstance(converted_value, int):
        return FuzzyInt(converted_value, tolerance_percent)

    return converted_value


def parse_ffprobe_frame_rate(raw_frame_rate: Union[int, float, str, None],
                            )-> Union[float, str, None]:
    value = number_if_possible(raw_frame_rate)
    if not isinstance(value, str):
        return value

    split = value.split('/')
    try:
        return float(split[0]) / float(split[1])
    except (ValueError, TypeError):
        return value


class FfprobeFormatReport:
    ATTRIBUTES_TO_COMPARE = {
        'format_name',
        'stream_types',
        'duration',
        'start_time',
        'program_count',
    }

    def __init__(self, raw_report: dict) -> None:
        self._raw_report = raw_report
        self._stream_reports = self._create_stream_reports(raw_report)

    @classmethod
    def _create_stream_report(cls, raw_stream_report: dict) -> \
            'FfprobeStreamReport':
        codec_type_to_report_class = {
            'video':    FfprobeVideoStreamReport,
            'audio':    FfprobeAudioStreamReport,
            'subtitle': FfprobeSubtitleStreamReport,
            'data':     FfprobeDataStreamReport,
        }

        codec_type = raw_stream_report['codec_type']
        if codec_type not in codec_type_to_report_class:
            raise UnsupportedCodecType(
                f"Unexpected codec type: {codec_type}. "
                f"A new stream report class is needed to handle it."
            )

        report_class = codec_type_to_report_class[codec_type]
        return report_class(raw_stream_report)

    @classmethod
    def _create_stream_reports(cls, raw_report: dict) -> \
            List['FfprobeStreamReport']:
        if 'streams' not in raw_report:
            return []

        return [
            cls._create_stream_report(raw_stream_report)
            for raw_stream_report in raw_report['streams']
        ]

    def select_streams(self, stream_type: str) -> List['FfprobeStreamReport']:
        return [
            stream
            for stream in self._stream_reports
            if stream.codec_type == stream_type
        ]

    @property
    def stream_reports(self) -> List['FfprobeStreamReport']:
        return self._stream_reports

    @property
    def stream_types(self) -> Dict[str, int]:
        streams = self._raw_report['streams']
        streams_dict: Dict[str, int] = {}

        for stream in streams:
            codec_type = stream['codec_type']
            if codec_type in streams_dict:
                streams_dict[codec_type] = streams_dict[codec_type] + 1
            else:
                streams_dict.update({codec_type: 1})
        return streams_dict

    @property
    def format_name(self) -> Optional[str]:
        return self._raw_report.get('format', {}).get('format_name', None)

    @property
    def duration(self) -> 'FuzzyDuration':
        return fuzzy_duration_if_possible(
            self._raw_report.get('format', {}).get('duration', None),
            0.1,
        )

    @property
    def start_time(self) -> Optional['FuzzyDuration']:
        return fuzzy_duration_if_possible(
            self._raw_report.get('format', {}).get('start_time', None),
            0.1,
        )

    @property
    def program_count(self) -> Optional[str]:
        return number_if_possible(
            self._raw_report.get('format', {}).get('nb_programs', None)
        )

    @classmethod
    def _classify_streams(cls,
                          stream_reports: List['FfprobeStreamReport'],
                         ) -> Dict[str, List['FfprobeStreamReport']]:
        reports_by_type: Dict[str, List['FfprobeStreamReport']] = {}
        for report in stream_reports:
            reports_by_type[report.codec_type] = (
                reports_by_type.get(report.codec_type, []) + [report]
            )

        return reports_by_type

    @classmethod
    def _diff_streams_same_type(cls,
                                actual_stream_reports:
                                List['FfprobeStreamReport'],
                                expected_stream_reports:
                                List['FfprobeStreamReport'],
                                overrides: Optional[FileOverrides] = None,
                                excludes: Optional[FileExcludes] = None,
                               ) -> Diff:
        assert len(
            set(r.codec_type for r in actual_stream_reports) |
            set(r.codec_type for r in expected_stream_reports)
        ) == 1, "All stream reports must have the same codec type"

        if overrides is None:
            overrides = {}
        if excludes is None:
            excludes = {}

        diffs: Diff = []

        unmatched_reports = set(range(len(expected_stream_reports)))
        for actual_idx, actual_report in enumerate(actual_stream_reports):
            shortest_diff: Optional[Diff] = None
            for expected_idx in unmatched_reports:
                new_diff = actual_report.diff(
                    expected_stream_reports[expected_idx],
                    overrides.get(
                        expected_stream_reports[expected_idx].codec_type,
                        {},
                    ),
                    excludes.get(
                        expected_stream_reports[expected_idx].codec_type,
                        set(),
                    ),
                )
                assert new_diff is not None

                if shortest_diff is None or len(shortest_diff) > len(new_diff):
                    assert new_diff is not None
                    shortest_diff = new_diff
                    matched_expected_stream_id = expected_idx
                    expected_stream_index = expected_stream_reports[expected_idx].index

                if len(shortest_diff) == 0:  # pylint: disable=len-as-condition
                    break

            if shortest_diff is not None:
                for diff_dict in shortest_diff:
                    diff_dict['actual_stream_index'] = actual_report.index
                    diff_dict['expected_stream_index'] = expected_stream_index

                diffs += shortest_diff
                unmatched_reports.remove(matched_expected_stream_id)
            else:
                diffs.append({
                    'location': actual_stream_reports[0].codec_type,
                    'actual_stream_index': actual_idx,
                    'expected_stream_index': None,
                    'reason': DiffReason.NoMatchingStream.value,
                })

        for expected_idx in unmatched_reports:
            diffs.append({
                'location': expected_stream_reports[0].codec_type,
                'actual_stream_index': None,
                'expected_stream_index':
                    expected_stream_reports[expected_idx].index,
                'reason': DiffReason.NoMatchingStream.value,
            })

        return diffs

    @classmethod
    def _diff_streams(cls,
                      actual_stream_reports: List['FfprobeStreamReport'],
                      expected_stream_reports: List['FfprobeStreamReport'],
                      overrides: Optional[FileOverrides] = None,
                      excludes: Optional[FileExcludes] = None,
                     ) -> Diff:

        actual_reports_by_type = cls._classify_streams(
            actual_stream_reports
        )
        expected_reports_by_type = cls._classify_streams(
            expected_stream_reports
        )
        codec_types_in_buckets = (
            set(actual_reports_by_type) |
            set(expected_reports_by_type)
        )

        stream_differences: Diff = []
        for codec_type in codec_types_in_buckets:
            stream_differences += cls._diff_streams_same_type(
                actual_reports_by_type.get(codec_type, []),
                expected_reports_by_type.get(codec_type, []),
                overrides,
                excludes,
            )

        return stream_differences

    # pylint: disable=unsubscriptable-object
    # FIXME: pylint bug, see https://github.com/PyCQA/pylint/issues/2377
    @classmethod
    def _diff_attributes(cls,
                         attributes_to_compare: Collection[str],
                         actual_report: 'FfprobeFormatReport',
                         expected_report: 'FfprobeFormatReport',
                         overrides: Optional[StreamOverrides] = None,
                         excludes: Optional[StreamExcludes] = None) -> Diff:
        if overrides is None:
            overrides = {}
        if excludes is None:
            excludes = set()

        differences = []
        for attribute in attributes_to_compare:
            actual_value = getattr(actual_report, attribute)
            expected_value = overrides.get(
                attribute,
                getattr(expected_report, attribute),
            )

            if attribute not in excludes and expected_value != actual_value:
                diff_dict = {
                    'location': 'format',
                    'attribute': attribute,
                    'actual_value': actual_value,
                    'expected_value': expected_value,
                    'reason': DiffReason.DifferentAttributeValues.value,
                }
                differences.append(diff_dict)

        return differences

    def diff(self,
             expected_report: 'FfprobeFormatReport',
             overrides: Optional[FileOverrides] = None,
             excludes: Optional[FileExcludes] = None) -> Diff:

        format_differences = self._diff_attributes(
            self.ATTRIBUTES_TO_COMPARE,
            self,
            expected_report,
            overrides.get('format', {}) if overrides is not None else None,
            excludes.get('format', set()) if excludes is not None else None,
        )

        stream_differences = self._diff_streams(
            self.stream_reports,
            expected_report.stream_reports,
            overrides,
            excludes,
        )

        return format_differences + stream_differences

    def __eq__(self, other):
        return len(self.diff(other)) == 0

    @classmethod
    def build(cls,
              tmp_dir: str,
              video_paths: List[str]) -> List['FfprobeFormatReport']:
        dirs_and_basenames: dict = {}
        for path in video_paths:
            dirname, basename = os.path.split(path)
            dirs_and_basenames[dirname] = (
                dirs_and_basenames.get(dirname, []) +
                [basename]
            )

        list_of_reports = []
        stream_operator = StreamOperator()

        for i, key in enumerate(dirs_and_basenames):
            metadata = stream_operator.get_metadata(
                dirs_and_basenames[key],
                key,
                os.path.join(tmp_dir, f"get-metadata-work-{i}/"),
                os.path.join(tmp_dir, f"get-metadata-output-{i}/"),
            )
            for path in metadata['data']:
                with open(path) as metadata_file:
                    list_of_reports.append(FfprobeFormatReport(
                        json.loads(metadata_file.read())
                    ))
        return list_of_reports

    def __repr__(self):
        messages = []
        for attr in self.ATTRIBUTES_TO_COMPARE:
            messages.append(f'{attr}: {str(getattr(self, attr))}')
        return f'FfprobeFormatReport({", ".join(messages)}. ' \
            f'Streams: {self.stream_reports.__repr__()})'


class FuzzyDuration:
    def __init__(self, duration: Union[float, int], tolerance: float) -> None:
        assert tolerance >= 0

        self._duration = duration
        self._tolerance = tolerance

    @property
    def duration(self) -> Any:
        return self._duration

    @property
    def tolerance(self) -> float:
        return self._tolerance

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            return abs(self.duration - other) <= self.tolerance

        if isinstance(other, FuzzyDuration):
            # We treat both fuzzy values as closed intervals:
            # [value - tolerance, value + tolerance]
            # If the intervals overlap at at least one point, we have a match.
            return (
                abs(self.duration - other.duration) <=
                self.tolerance + other.tolerance
            )

        return self._duration == other


    def __str__(self):
        if self._tolerance == 0:
            return f'{self._duration}'

        return f'{self._duration}[+/-{self._tolerance}]'

    def __repr__(self):
        return f'FuzzyDuration({self._duration}, {self._tolerance})'


class FuzzyInt:
    def __init__(self, value: int, tolerance_percent: int) -> None:
        assert tolerance_percent >= 0

        self._value = value
        self._tolerance_percent = tolerance_percent

    @property
    def value(self) -> int:
        return self._value

    @property
    def tolerance_percent(self) -> int:
        return self._tolerance_percent

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            return (
                abs(self.value - other) <=
                self.tolerance_percent * self.value
            )

        if isinstance(other, FuzzyInt):
            tolerance = (
                abs(self.tolerance_percent * self.value) +
                abs(other.tolerance_percent * other.value)
            ) / 100
            return abs(self.value - other.value) <= tolerance

        return self.value == other

    def __str__(self):
        if self.tolerance_percent == 0:
            return f'{self._value}'

        return f'{self._value}[+/-{self.tolerance_percent}%]'

    def __repr__(self):
        return f'FuzzyInt({self._value}, {self.tolerance_percent})'


class FfprobeStreamReport:
    ATTRIBUTES_TO_COMPARE = {
        'codec_type',
        'codec_name',
        'start_time'
    }

    def __init__(self, raw_report: dict) -> None:
        assert 'codec_type' in raw_report

        self._raw_report = raw_report

    @property
    def codec_type(self) -> str:
        return self._raw_report['codec_type']

    @property
    def codec_name(self)-> Optional[str]:
        return self._raw_report.get('codec_name', None)

    @property
    def start_time(self) -> FuzzyDuration:
        return fuzzy_duration_if_possible(
            self._raw_report.get('start_time'),
            0.1,
        )

    @property
    def index(self) -> int:
        return self._raw_report['index']

    # pylint: disable=unsubscriptable-object
    # FIXME: pylint bug, see https://github.com/PyCQA/pylint/issues/2377
    @classmethod
    def _diff_attributes(cls,
                         attributes_to_compare: Collection[str],
                         actual_stream_report: 'FfprobeStreamReport',
                         expected_stream_report: 'FfprobeStreamReport',
                         overrides: Optional[StreamOverrides] = None,
                         excludes: Optional[StreamExcludes] = None) -> Diff:

        assert (actual_stream_report.codec_type ==
                expected_stream_report.codec_type)

        if overrides is None:
            overrides = {}
        if excludes is None:
            excludes = set()

        differences = []
        for attribute in attributes_to_compare:
            actual_value = getattr(actual_stream_report, attribute)
            expected_value = overrides.get(
                attribute,
                getattr(expected_stream_report, attribute),
            )

            if (
                    attribute not in excludes and
                    expected_value != actual_value
            ):
                diff_dict = {
                    'location': actual_stream_report.codec_type,
                    'attribute': attribute,
                    'actual_value': actual_value,
                    'expected_value': expected_value,
                    'reason': DiffReason.DifferentAttributeValues.value,
                }
                differences.append(diff_dict)

        return differences

    def diff(self,
             expected_stream_report: 'FfprobeStreamReport',
             overrides: Optional[StreamOverrides] = None,
             excludes: Optional[StreamExcludes] = None) -> Diff:

        return self._diff_attributes(
            self.ATTRIBUTES_TO_COMPARE,
            self,
            expected_stream_report,
            overrides,
            excludes,
        )

    def __eq__(self, other):
        return len(self.diff(other)) == 0

    def __repr__(self):
        messages = []
        for attr in self.ATTRIBUTES_TO_COMPARE:
            messages.append(f'{attr}: {str(getattr(self, attr))}')
        return f'{type(self).__name__}({", ".join(messages)} )'


class FfprobeAudioAndVideoStreamReport(FfprobeStreamReport):
    ATTRIBUTES_TO_COMPARE = FfprobeStreamReport.ATTRIBUTES_TO_COMPARE | {
        'duration',
        'bitrate',
        'frame_count',
    }

    @property
    def duration(self) -> FuzzyDuration:
        return fuzzy_duration_if_possible(self._raw_report.get('duration'), 0.1)

    @property
    def bitrate(self) -> FuzzyInt:
        return fuzzy_int_if_possible(self._raw_report.get('bit_rate'), 5)

    @property
    def frame_count(self) -> Union[str, Any]:
        return number_if_possible(self._raw_report.get('nb_frames'))


class FfprobeVideoStreamReport(FfprobeAudioAndVideoStreamReport):
    ATTRIBUTES_TO_COMPARE = \
        FfprobeAudioAndVideoStreamReport.ATTRIBUTES_TO_COMPARE | {
            'resolution',
            'pixel_format',
            'frame_rate',
        }

    def __init__(self, raw_report: dict) -> None:
        assert raw_report['codec_type'] == 'video'
        super().__init__(raw_report)

    @property
    def resolution(self) -> Union[Collection, list]:
        resolution = self._raw_report.get('resolution', None)
        width = self._raw_report.get('width', None)
        height = self._raw_report.get('height', None)

        if resolution is None and width is not None and height is not None:
            return [width, height]
        if resolution is not None and width is None and height is None:
            return resolution

        is_collection = isinstance(resolution, Collection)
        if is_collection and resolution == [width, height]:
            return resolution

        return [resolution, width, height]

    @property
    def pixel_format(self) -> Optional[str]:
        return self._raw_report.get('pix_fmt')

    @property
    def frame_rate(self)-> Union[float, str, None]:
        return parse_ffprobe_frame_rate(self._raw_report.get('r_frame_rate'))


class FfprobeAudioStreamReport(FfprobeAudioAndVideoStreamReport):
    def __init__(self, raw_report: dict) -> None:
        assert raw_report['codec_type'] == 'audio'
        super().__init__(raw_report)

    ATTRIBUTES_TO_COMPARE = \
        FfprobeAudioAndVideoStreamReport.ATTRIBUTES_TO_COMPARE | {
            'sample_rate',
            'sample_format',
            'channel_count',
            'channel_layout',
        }

    @property
    def sample_rate(self)-> Union[int, Any]:
        return number_if_possible(self._raw_report.get('sample_rate'))

    @property
    def sample_format(self) -> Optional[str]:
        return self._raw_report.get('sample_format')

    @property
    def channel_count(self)-> Optional[int]:
        return number_if_possible(self._raw_report.get('channels'))

    @property
    def channel_layout(self)-> Optional[str]:
        return self._raw_report.get('channel_layout')


class FfprobeSubtitleStreamReport(FfprobeStreamReport):
    def __init__(self, raw_report: dict) -> None:
        assert raw_report['codec_type'] == 'subtitle'
        super().__init__(raw_report)

    ATTRIBUTES_TO_COMPARE = FfprobeStreamReport.ATTRIBUTES_TO_COMPARE | {
        'language',
    }

    @property
    def language(self):
        return self._raw_report.get('tags', {}).get('language')


class FfprobeDataStreamReport(FfprobeStreamReport):
    def __init__(self, raw_report: dict) -> None:
        assert raw_report['codec_type'] == 'data'
        super().__init__(raw_report)
