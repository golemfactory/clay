import json
import os
from typing import Any, Collection, Dict, List, Optional, Tuple, Union

from apps.transcoding.ffmpeg.utils import StreamOperator


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
        return FuzzyDuration(
            self._raw_report.get('format', {}).get('duration', None),
            0.1,
        )

    @property
    def start_time(self) -> Optional['FuzzyDuration']:
        return FuzzyDuration(
            self._raw_report.get('format', {}).get('start_time', None),
            0.1,
        )

    @property
    def program_count(self) -> Optional[str]:
        return self._raw_report.get('format', {}).get('nb_programs', None)

    def diff(self, format_report: dict, overrides: Optional[dict] = None):
        if overrides is None:
            overrides = {}

        differences = list()
        for attr in self.ATTRIBUTES_TO_COMPARE:
            original_value = getattr(self, attr)
            modified_value = getattr(format_report, attr)

            if 'streams' in overrides and attr in overrides['streams']:
                modified_value = overrides['streams'][attr]

            if 'format' in overrides and attr in overrides['format']:
                modified_value = overrides['format'][attr]

            if modified_value != original_value:
                diff_dict = {
                    'location': 'format',
                    'attribute': attr,
                    'original value': original_value,
                    'modified value': modified_value,
                }
                differences.append(diff_dict)
        return differences

    def __eq__(self, other):
        return len(self.diff(other)) == 0

    @classmethod
    def build(cls, *video_paths: str) -> List['FfprobeFormatReport']:
        dirs_and_basenames: dict = {}
        for path in video_paths:
            dirname, basename = os.path.split(path)
            dirs_and_basenames[dirname] = (
                dirs_and_basenames.get(dirname, []) +
                [basename]
            )

        list_of_reports = []
        stream_operator = StreamOperator()

        for key in dirs_and_basenames:
            metadata = stream_operator.get_metadata(
                dirs_and_basenames[key],
                key
            )
            for path in metadata['data']:
                with open(path) as metadata_file:
                    list_of_reports.append(FfprobeFormatReport(
                        json.loads(metadata_file.read())
                    ))
        return list_of_reports


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
        if not isinstance(other, FuzzyDuration):
            return self._duration == other

        # We treat both fuzzy values as closed intervals:
        # [value - tolerance, value + tolerance]
        # If the intervals overlap at at least one point, we have a match.
        return abs(self.duration - other.duration) <= \
               self.tolerance + other.tolerance

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
        if not isinstance(other, FuzzyInt):
            return self._value == other

        tolerance = (
            abs(self.tolerance_percent * self.value) +
            abs(other.tolerance_percent * other.value)
        ) / 100
        return abs(self.value - other.value) <= tolerance

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
    def codec_type(self) -> Optional[str]:
        return self._raw_report.get('codec_type', None)

    @property
    def codec_name(self)-> Optional[str]:
        return self._raw_report.get('codec_name', None)

    @property
    def start_time(self) -> FuzzyDuration:
        return FuzzyDuration(
            self._raw_report.get('start_time'),
            0.1,
        )

    def __eq__(self, other):
        return len(self.diff(other)) == 0


class FfprobeAudioAndVideoStreamReport(FfprobeStreamReport):
    ATTRIBUTES_TO_COMPARE = FfprobeStreamReport.ATTRIBUTES_TO_COMPARE | {
        'duration',
        'bitrate',
        'frame_count',
    }

    @property
    def duration(self) -> FuzzyDuration:
        return FuzzyDuration(self._raw_report.get('duration'), 0.1)

    @property
    def bitrate(self) -> FuzzyInt:
        return FuzzyInt(self._raw_report.get('bit_rate'), 5)

    @property
    def frame_count(self) -> Union[str, Any]:
        return self._raw_report.get('nb_frames')


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
    def resolution(self) -> Union[Collection, Tuple[Collection, Any, Any]]:
        return (
            self._raw_report.get('resolution', None),
            self._raw_report.get('width', None),
            self._raw_report.get('height', None),
        )

    @property
    def pixel_format(self) -> Optional[str]:
        return self._raw_report.get('pix_fmt')

    @property
    def frame_rate(self)-> Union[float, str, None]:
        frame_rate = self._raw_report.get('r_frame_rate')
        if isinstance(frame_rate, (int, float)):
            return frame_rate
        elif isinstance(frame_rate, str):
            split = frame_rate.split('/')
            try:
                return float(split[0]) / float(split[1])
            except (ValueError, TypeError):
                pass
        return self._raw_report.get('r_frame_rate')

    def diff(self,
             format_report: dict,
             overrides: Optional[dict] = None) -> list:

        if overrides is None:
            overrides = {}

        differences = list()
        for attr in self.ATTRIBUTES_TO_COMPARE:
            original_value = getattr(self, attr)
            modified_value = getattr(format_report, attr)

            if modified_value != original_value:
                diff_dict = {
                    'location': 'video',
                    'attribute': attr,
                    'original value': original_value,
                    'modified value': modified_value,
                }
                differences.append(diff_dict)
        return differences


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
        return int(self._raw_report.get('sample_rate'))

    @property
    def sample_format(self) -> Optional[str]:
        return self._raw_report.get('sample_format')

    @property
    def channel_count(self)-> Optional[int]:
        return self._raw_report.get('channels')

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
