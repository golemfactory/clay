import json
from enum import Enum
from typing import Any, Dict, Tuple

from apps.core.task.coretask import CoreTask, CoreTaskTypeInfo, CoreTaskBuilder
from apps.core.task.coretaskstate import TaskDefinition
from golem.core.common import HandleKeyError, HandleError



#task.base.initialize


class TranscodingTypeInfo(CoreTaskTypeInfo):
    def __init__(self):
        super().__init__('Transcoding', TranscodingTaskDefinition, TranscodingTaskDefaults(), TranscodingTaskOptions, TranscodingTaskBuilder)
        self.output_formats = [] # TODO
        self.output_file_ext = [] # TODO






def unsupported(name: str):
    raise TranscodingTaskBuilderExcpetion('{} is not supported'.format(name))


class VideoCodec(Enum):
    #This is a list all supported video codecs by one of our transcoders
    #(for instance ffmpeg)
    AV1 = 'AV1'
    H_264 = 'H.264'
    MPEG_2 = 'MPEG-2'
    MPEG_4 = 'MPEG-4'
    MPEG_4_Part_2 = 'MPEG-4 Part 2'

    @staticmethod
    @HandleKeyError(unsupported)
    def from_name(name: str) -> VideoCodec:
        return VideoCodec(name.lower())


class AudioCodec(Enum):
    # This is a list all supported audio codecs by one of our transcoders
    # (for instance ffmpeg)
    MP3 = 'MP3'
    AAC = 'AAC'

    @staticmethod
    @HandleKeyError(unsupported)
    def from_name(name: str) -> AudioCodec:
        return AudioCodec(name.lower())


class VideoFileFormat(Enum):
    MP4 = 'mp4'
    AVI = 'avi'
    MKV = 'mkv'

    @staticmethod
    @HandleKeyError(unsupported)
    def from_name(name: str) -> VideoFileFormat:
        return VideoFileFormat(name.lower())

    def get_supported_video_codecs(self):
        return map(lambda v, a: v, FILE_FORMAT_SUPPORTED_CODECS[self]) # UWAGA NA TO MAPOWANIE

    def get_supported_audio_codecs(self):
        return map(lambda v, a: a, FILE_FORMAT_SUPPORTED_CODECS[self]) # UWAGA NA TO MAPOWANIE


ALL = ([c for c in VideoCodec], [c for c in AudioCodec])
FILE_FORMAT_SUPPORTED_CODECS = {
    VideoFileFormat.AVI: ALL,
    VideoFileFormat.MKV: ALL,
    VideoFileFormat.MP4: ([VideoCodec.H_264, VideoCodec.MPEG_4_Part_2,
                           VideoCodec.MPEG_2, VideoCodec.MPEG_1],
                          [AudioCodec.AAC, AudioCodec.MP3])
}

# TODO:
# Czy typować? Co robia inni (A?)
# Czym sie rozni minimal definition od full?
# poprawic impoorty
# Co to są property?


class TranscodingTaskDefinition(TaskDefinition):
    class TranscodingAudioParams:
        def __init__(self, codec: AudioCodec, bitrate: int = None):
            self.codec = codec
            self.bitrate = bitrate

    class TranscodingVideoParams:
        def __init__(self, codec: VideoCodec, bit_rate = None, frame_rate: int = None,
                     resolution: Tuple[int, int] = None):
            self.codec = codec
            self.bit_rate = bit_rate
            self.frame_rate = frame_rate
            self.resolution = resolution

    def __init__(self, input_stream_path, audio_params, video_params):
        super().__init__()
        self.input_stream_path = input_stream_path
        self.audio_params = audio_params
        self.video_params = video_params


class TranscodingTaskBuilderExcpetion(Exception):
    pass


class TranscodingTaskBuilder(CoreTaskBuilder):
    # jako property
    SUPPORTED_FILE_TYPES = []
    SUPPORTED_VIDEO_CODECS = []
    SUPPORTED_AUDIO_CODECS = []

    @classmethod
    def build_full_definition(cls, task_type: CoreTaskTypeInfo,
                              dict: Dict[str, Any]):
        super().build_full_definition(task_type, dict)
        input_stream_path = dict.get('resources', [''])[0]
        presets = cls._get_presets(input_stream_path)
        options = dict.get('options', {})
        video_options = options.get('video', {})
        audio_options = options.get('audio', {})

        audio_params = TranscodingTaskDefinition.TranscodingAudioParams(
            AudioCodec.from_name(audio_options.get('codec')),
            audio_options.get('bit_rate'))

        video_params = TranscodingTaskDefinition.TranscodingVideoParams(
            VideoCodec.from_name(video_options.get('codec')),
            video_options.get('bit_rate', presets.get('video_bit_rate')))

        task_def = TranscodingTaskDefinition(input_stream_path, audio_params,
                                             video_params)

        task_def.video_params.target_encoding = dict['target_encoding']
        return task_def

    @classmethod
    def build_minimal_definition(cls, task_type: CoreTaskTypeInfo,
                                 dict: Dict[str, Any]):
        # I cannot imagine what minimal definition means in transcoding task
        return cls.build_full_definition(task_type, dict)

    @classmethod
    def get_supported_video_codecs(cls, filetype: VideoFileFormat = None):
        if filetype:
            return set(filetype.get_supported_video_codecs())\
                .intersection(cls.SUPPORTED_VIDEO_CODECS) # robienie set'a
        return cls.SUPPORTED_VIDEO_CODECS

    @classmethod
    def get_supported_audio_codecs(cls, filetype: VideoFileFormat = None):
        if filetype:
            return set(filetype.get_supported_audio_codecs()) \
                .intersection(cls.SUPPORTED_AUDIO_CODECS)  # robienie set'a
        return cls.SUPPORTED_VIDEO_CODECS

    @classmethod
    @HandleError(ValueError, lambda *_, **__: {})
    @HandleError(IOError, lambda *_, **__: {})
    # ADD LOGGS
    def _get_presets(cls, path: str) -> Dict[str, Any]:
        # EXECUTE COMMAND TO GET METADATA AND ADD LOGGING
        with open(path) as f:
            return json.load(f)


class ffmpegTaskBuilder(TranscodingTaskBuilder):
    SUPPORTED_FILE_TYPES = [VideoFileFormat.MKV, VideoFileFormat.AVI,
                            VideoFileFormat.MP4]
    SUPPORTED_VIDEO_CODECS = [VideoCodec.AV1, VideoCodec.MPEG_2, VideoCodec.H_264]
    SUPPORTED_AUDIO_CODECS = [AudioCodec.MP3, AudioCodec.AAC]
