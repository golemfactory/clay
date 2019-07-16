import pytest
from parameterized import parameterized

from ffmpeg_tools.codecs import VideoCodec
from ffmpeg_tools.formats import Container

from golem.testutils import remove_temporary_dirtree_if_test_passed
from golem.tools.ci import ci_skip
from tests.apps.ffmpeg.task.ffmpeg_integration_base import \
    FfmpegIntegrationBase


# flake8: noqa
# pylint: disable=line-too-long,bad-whitespace
VIDEO_FILES = [
    # Files from the repo
    {"resolution": [320, 240],   "container": Container.c_MP4,      "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "test_video.mp4"},
    {"resolution": [320, 240],   "container": Container.c_MP4,      "video_codec": VideoCodec.H_264,     "key_frames": 2,    "path": "test_video2"},

    # Files from transcoding-video-bundle
    {"resolution": [512, 288],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 1,    "path": "videos/good/basen-out8[vp8,512x288,10s,v1a0s0d0,i248p494b247,25fps].webm"},
    {"resolution": [512, 288],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP9,       "key_frames": 1,    "path": "videos/good/basen-out9[vp9,512x288,10s,v1a0s0d0,i248p494b247,25fps].webm"},
    {"resolution": [1920, 1080], "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 15,   "path": "videos/good/beachfront-dandelion[mpeg2video+mp2,1920x1080,20s,v1a1s0d0,i1765p1925b1604,23.976fps][segment1of11].mpeg"},
    {"resolution": [1920, 1080], "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/beachfront-mooncloseup[wmv3,1920x1080,34s,v1a0s0d0,i799p1578b792,24fps][segment1of7].wmv"},
    {"resolution": [1920, 1080], "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/beachfront-sleepingbee[wmv3+wmapro,1920x1080,47s,v1a1s0d0,i1135p2241b1125,24fps][segment1of10].wmv"},
    {"resolution": [1920, 960],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.HEVC,      "key_frames": 1,    "path": "videos/good/h265files-alps[hevc+aac,1920x960,16s,v1a1s0d0,i401p478b718,25fps][segment1of2].mkv"},
    {"resolution": [854, 480],   "container": Container.c_MATROSKA, "video_codec": VideoCodec.MSMPEG4V2, "key_frames": 4,    "path": "videos/good/matroska-test1[msmpeg4v2+mp3,854x480,87s,v1a1s0d0,i4215p6261b4190,24fps][segment1of10].mkv"},
    {"resolution": [1024, 576],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.H_264,     "key_frames": 5,    "path": "videos/good/matroska-test5[h264+aac+aac,1024x576,47s,v1a2s8d0,i1149p1655b1609,24fps][segment1of10].mkv"},
    {"resolution": [1280, 720],  "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 11,   "path": "videos/good/natureclip-fireandembers[wmv3+wmav2,1280x720,63s,v1a1s0d0,i2240p3428b1889,29.97fps][segment1of13].wmv"},
    {"resolution": [176, 144],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 7,    "path": "videos/good/sample-bigbuckbunny[h263+amr_nb,176x144,41s,v1a1s0d0,i1269p1777b1218,15fps][segment1of9].3gp"},
    # ffmpeg does not transcode this file correctly. It’s missing a lot of
    # frames. We have decided to disable it because the file is likely
    # damaged, nonstandard or uses a format feature that ffmpeg can’t handle.
    # The broken file is unfortunately the expected result because that’s
    # how ffmpeg processes the file - it’s not a bug in our code. In the
    # future it would be better to find a way to weed out files like this at
    # the validation stage
    # {"resolution": [1280, 720],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.MPEG_4,    "key_frames": 1,    "path": "videos/good/sample-bigbuckbunny[mpeg4+aac,1280x720,4s,v1a1s0d0,i293p438b292,25fps].mkv"},
    {"resolution": [320, 240],   "container": Container.c_3GP,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 11,   "path": "videos/good/sample-bigbuckbunny[mpeg4+aac,320x240,15s,v1a1s0d0,i780p1091b748,25fps][segment1of3].3gp"},
    {"resolution": [640, 368],   "container": Container.c_MP4,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 1,    "path": "videos/good/sample-bigbuckbunny[mpeg4+aac,640x368,6s,v1a1s0d0,i319p477b318,25fps].mp4"},
    {"resolution": [560, 320],   "container": Container.c_AVI,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 13,   "path": "videos/good/standalone-bigbuckbunny[mpeg4+mp3,560x320,6s,v1a1s0d0,i344p482b330,30fps][segment1of2].avi"},
    {"resolution": [180, 140],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/standalone-catherine[wmv3+wmav2,180x140,42s,v1a1s0d0,i637p1257b631,_][segment1of6].wmv"},
    {"resolution": [400, 300],   "container": Container.c_MOV,      "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-dlppart2[h264+aac,400x300,129s,v1a1s0d0,i3874p4884b6671,29.97fps][segment1of17].mov"},
    {"resolution": [720, 480],   "container": Container.c_IPOD,     "video_codec": VideoCodec.H_264,     "key_frames": 2,    "path": "videos/good/standalone-dolbycanyon[h264+aac,720x480,38s,v1a1s0d0,i1147p1466b1948,29.97fps][segment1of5].m4v"},
    {"resolution": [720, 480],   "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 13,   "path": "videos/good/standalone-grb2[flv1,720x480,28s,v1a0s0d0,i1743p2428b1668,29.9697fps][segment1of6].flv"},
    {"resolution": [720, 480],   "container": Container.c_IPOD,     "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-grb2[h264,720x480,28s,v1a0s0d0,i840p1060b1437,29.97fps][segment1of4].m4v"},
    {"resolution": [720, 480],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 47,   "path": "videos/good/standalone-grb2[mpeg2video,720x480,28s,v1a0s0d0,i2596p2783b3103,29.97fps].mpg"},
    {"resolution": [720, 480],   "container": Container.c_SVCD,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 13,   "path": "videos/good/standalone-grb2[mpeg2video,720x480,28s,v1a0s0d0,i2656p3337b2579,29.97fps][segment1of6].vob"},
    {"resolution": [720, 480],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV2,      "key_frames": 13,   "path": "videos/good/standalone-grb2[wmv2,720x480,28s,v1a0s0d0,i1744p2427b1668,29.97fps][segment1of6].wmv"},
    {"resolution": [1920, 1080], "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 10,   "path": "videos/good/standalone-jellyfish[flv1,1920x1080,30s,v1a0s0d0,i1874p2622b1798,29.9697fps][segment1of8].flv"},
    {"resolution": [1408, 1152], "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 10,   "path": "videos/good/standalone-jellyfish[h263,1408x1152,30s,v1a0s0d0,i1874p2622b1798,29.97fps][segment1of8].3gp"},
    {"resolution": [1920, 1080], "container": Container.c_MATROSKA, "video_codec": VideoCodec.HEVC,      "key_frames": 1,    "path": "videos/good/standalone-jellyfish[hevc,1920x1080,30s,v1a0s0d0,i903p1123b1571,29.97fps][segment1of4].mkv"},
    # This file fails at the transcoding step because the result of the
    # extract+split step is incorrect - it still contains an audio track.
    # We have decided to disable this case because the file is likely
    # damaged, nonstandard or uses a format feature that ffmpeg can’t handle.
    # The failure is the expected result unless we find a way to block this
    # file via validations.“
    # {"resolution": [384, 288],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_1,    "key_frames": 8,    "path": "videos/good/standalone-lion[mpeg1video+mp2,384x288,117s,v1a1s0d0,i8738p9088b10660,23.976fps][segment1of24].mpeg"},
    {"resolution": [320, 240],   "container": Container.c_MP4,      "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-p6090053[h264+aac,320x240,30s,v1a1s0d0,i376p468b653,12.5fps][segment1of2].mp4"},
    {"resolution": [320, 240],   "container": Container.c_MOV,      "video_codec": VideoCodec.MJPEG,     "key_frames": 38,   "path": "videos/good/standalone-p6090053[mjpeg+pcm_u8,320x240,30s,v1a1s0d0,i1123p748b748,12.5fps][segment1of10].mov"},
    {"resolution": [480, 270],   "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 11,   "path": "videos/good/standalone-page18[flv1+mp3,480x270,216s,v1a1s0d0,i11252p15749b10800,25fps][segment1of44].flv"},
    {"resolution": [352, 288],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 11,   "path": "videos/good/standalone-page18[h263+amr_nb,352x288,216s,v1a1s0d0,i11252p15749b10800,25fps][segment1of44].3gp"},
    {"resolution": [480, 270],   "container": Container.c_IPOD,     "video_codec": VideoCodec.H_264,     "key_frames": 2,    "path": "videos/good/standalone-page18[h264+aac,480x270,216s,v1a1s0d0,i5446p10755b5400,25fps][segment1of43].m4v"},
    {"resolution": [480, 270],   "container": Container.c_AVI,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 11,   "path": "videos/good/standalone-page18[mpeg4+mp3,480x270,216s,v1a1s0d0,i11252p15749b10800,25fps][segment1of44].avi"},
    {"resolution": [1920, 1080], "container": Container.c_MPEGTS,   "video_codec": VideoCodec.H_264,     "key_frames": 11,   "path": "videos/good/standalone-panasonic[h264+ac3,1920x1080,46s,v1a1s1d0,i1247p1439b1919,25fps][segment1of10].mts"},
    {"resolution": [1920, 1080], "container": Container.c_AVI,      "video_codec": VideoCodec.MPEG_4,    "key_frames": 11,   "path": "videos/good/standalone-panasonic[mpeg4+mp3,1920x1080,46s,v1a1s0d0,i2401p3355b2302,25fps][segment1of10].avi"},
    {"resolution": [352, 288],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 13,   "path": "videos/good/standalone-small[h263+amr_nb,352x288,6s,v1a1s0d0,i344p482b330,30fps][segment1of2].3gp"},
    {"resolution": [560, 320],   "container": Container.c_MPEGTS,   "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-small[h264+ac3,560x320,6s,v1a1s0d0,i166p211b284,29.97fps].mts"},
    {"resolution": [560, 320],   "container": Container.c_MATROSKA, "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-small[h264+vorbis,560x320,6s,v1a1s0d0,i166p211b284,30fps].mkv"},
    {"resolution": [560, 320],   "container": Container.c_SVCD,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 13,   "path": "videos/good/standalone-small[mpeg2video+mp2,560x320,6s,v1a1s0d0,i523p661b509,30fps][segment1of2].vob"},
    {"resolution": [560, 320],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 1,    "path": "videos/good/standalone-small[vp8+vorbis,560x320,6s,v1a1s0d0,i166p330b165,30fps].webm"},
    {"resolution": [560, 320],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV2,      "key_frames": 13,   "path": "videos/good/standalone-small[wmv2+wmav2,560x320,6s,v1a1s0d0,i344p482b330,30fps][segment1of2].wmv"},
    {"resolution": [1280, 720],  "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 11,   "path": "videos/good/standalone-startrails[flv1+mp3,1280x720,21s,v1a1s0d0,i1101p1540b1056,25fps][segment1of5].flv"},
    {"resolution": [704, 576],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 11,   "path": "videos/good/standalone-startrails[h263+amr_nb,704x576,21s,v1a1s0d0,i1101p1540b1056,25fps][segment1of5].3gp"},
    {"resolution": [1280, 720],  "container": Container.c_WEBM,     "video_codec": VideoCodec.VP9,       "key_frames": 1,    "path": "videos/good/standalone-startrails[vp9+opus,1280x720,21s,v1a1s0d0,i533p1052b528,25fps][segment1of5].webm"},
    {"resolution": [704, 576],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 12,   "path": "videos/good/standalone-tra3106[h263,704x576,17s,v1a0s0d0,i1069p1472b1016,29.97fps][segment1of5].3gp"},
    {"resolution": [720, 496],   "container": Container.c_AVI,      "video_codec": VideoCodec.MJPEG,     "key_frames": 30,   "path": "videos/good/standalone-tra3106[mjpeg,720x496,17s,v1a0s0d0,i1525p1016b1016,29.97fps][segment1of17].avi"},
    {"resolution": [320, 240],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV1,      "key_frames": 2,    "path": "videos/good/standalone-video1[wmv1+wmav2,320x240,12s,v1a1s0d0,i703p1048b700,30fps][segment1of2].wmv"},
    {"resolution": [320, 240],   "container": Container.c_FLV,      "video_codec": VideoCodec.FLV1,      "key_frames": 4,    "path": "videos/good/standalone-videosample[flv1,320x240,59s,v1a0s0d0,i491p625b446,_][segment1of12].flv"},
    {"resolution": [320, 240],   "container": Container.c_MPEGTS,   "video_codec": VideoCodec.H_264,     "key_frames": 1,    "path": "videos/good/standalone-videosample[h264,320x240,59s,v1a0s0d0,i224p279b390,29.97fps].mts"},
    {"resolution": [320, 240],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV2,      "key_frames": 1,    "path": "videos/good/techslides-small[wmv2+wmav2,320x240,6s,v1a1s0d0,i331p495b330,30fps].wmv"},
    {"resolution": [640, 360],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 3,    "path": "videos/good/webmfiles-bigbuckbunny[vp8+vorbis,640x360,32s,v1a1s0d0,i837p1597b811,25fps][segment1of7].webm"},
    {"resolution": [640, 480],   "container": Container.c_ASF,      "video_codec": VideoCodec.WMV3,      "key_frames": 1,    "path": "videos/good/wfu-katamari[wmv3+wmav2,640x480,10s,v1a1s0d0,i301p597b299,29.97fps][segment1of2].wmv"},
    {"resolution": [3840, 2160], "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 13,   "path": "videos/good/wikipedia-globaltemp[vp8+vorbis,3840x2160,37s,v1a1s0d0,i1194p2113b1102,30fps][segment1of8].webm"},
    {"resolution": [1920, 1080], "container": Container.c_WEBM,     "video_codec": VideoCodec.VP8,       "key_frames": 1,    "path": "videos/good/wikipedia-tractor[vp8+vorbis,1920x1080,28s,v1a1s0d0,i695p1373b689,1000fps][segment1of5].webm"},
    {"resolution": [854, 480],   "container": Container.c_WEBM,     "video_codec": VideoCodec.VP9,       "key_frames": 1,    "path": "videos/good/wikipedia-tractor[vp9+opus,854x480,28s,v1a1s0d0,i692p1376b689,25fps][segment1of3].webm"},
    {"resolution": [854, 480],   "container": Container.c_WEBM,     "video_codec": VideoCodec.AV1,       "key_frames": 1880, "path": "videos/good/woolyss-llamadrama[av1+opus,854x480,87s,v1a1s0d0,i1879p1879b1879,24fps].webm"},
    {"resolution": [1920, 1080], "container": Container.c_MOV,      "video_codec": VideoCodec.MJPEG,     "key_frames": 1192, "path": "videos/bad/beachfront-moonandclouds[mjpeg,1920x1080,50s,v1a0s0d1,i3574p2382b2382,24fps].mov"},
    {"resolution": [1920, 1080], "container": Container.c_MOV,      "video_codec": VideoCodec.MJPEG,     "key_frames": 792,  "path": "videos/bad/beachfront-mooncloseup[mjpeg,1920x1080,33s,v1a0s0d1,i2374p1582b1582,23.976fps].mov"},
    {"resolution": [1280, 720],  "container": Container.c_MATROSKA, "video_codec": VideoCodec.THEORA,    "key_frames": 36,   "path": "videos/bad/matroska-test4[theora+vorbis,1280x720,_,v1a1s0d0,i1677p3247b1641,24fps].mkv"},
    {"resolution": [1920, 1080], "container": Container.c_MOV,      "video_codec": VideoCodec.H_264,     "key_frames": 7,    "path": "videos/bad/natureclip-relaxriver[h264+aac,1920x1080,20s,v1a1s0d1,i606p1192b599,29.97fps].mov"},
    {"resolution": [704, 576],   "container": Container.c_3GP,      "video_codec": VideoCodec.H_263,     "key_frames": 96,   "path": "videos/bad/standalone-dolbycanyon[h263+amr_nb,704x576,38s,v1a1s0d0,i2376p3325b2280,29.97fps].3gp"},
    {"resolution": [720, 480],   "container": Container.c_SVCD,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 77,   "path": "videos/bad/standalone-dolbycanyon[mpeg2video+ac3,720x480,38s,v1a1s0d1,i3574p3801b4257,29.97fps].vob"},
    {"resolution": [560, 320],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 14,   "path": "videos/bad/standalone-small[mpeg2video+mp2,560x320,6s,v1a1s0d1,i523p661b509,30fps].mpg"},
    {"resolution": [720, 496],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 59,   "path": "videos/bad/standalone-tra3106[mpeg2video,720x496,17s,v1a0s0d1,i1642p2033b1583,29.97fps].mpeg"},
    {"resolution": [320, 240],   "container": Container.c_MPEG,     "video_codec": VideoCodec.MPEG_2,    "key_frames": 1188, "path": "videos/bad/standalone-videosample[mpeg2video,320x240,59s,v1a0s0d1,i45135p57013b43947,240fps].mpg"},
    {"resolution": [560, 320],   "container": Container.c_OGG,      "video_codec": VideoCodec.THEORA,    "key_frames": 3,    "path": "videos/bad/techslides-small[theora+vorbis,560x320,6s,v1a1s0d1,i168p328b165,30fps].ogv"},
]
# pylint: enable=line-too-long,bad-whitespace


@ci_skip
class TestFfmpegIntegrationFullBundleSet(FfmpegIntegrationBase):

    @parameterized.expand(
        (
            (video, video_codec, container)
            for video in VIDEO_FILES
            for video_codec, container in [
                (VideoCodec.FLV1, Container.c_FLV),
                (VideoCodec.H_264, Container.c_AVI),
                (VideoCodec.HEVC, Container.c_MP4),
                (VideoCodec.MJPEG, Container.c_MOV),
                (VideoCodec.MPEG_1, Container.c_MPEG),
                (VideoCodec.MPEG_2, Container.c_MPEG),
                (VideoCodec.MPEG_4, Container.c_MPEGTS),
                (VideoCodec.THEORA, Container.c_OGG),
                (VideoCodec.VP8, Container.c_WEBM),
                (VideoCodec.VP9, Container.c_MATROSKA),
                (VideoCodec.WMV1, Container.c_ASF),
                (VideoCodec.WMV2, Container.c_ASF),
            ]
        ),
        testcase_func_name=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_from_"
            f"{param[0][0]['video_codec'].value}_"
            f"{param[0][0]['container'].value}_to_"
            f"{param[0][1].value}_"
            f"{param[0][2].value}"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_codec_change(self,
                                               video,
                                               video_codec,
                                               container):
        super().split_and_merge_with_codec_change(video, video_codec, container)

    @parameterized.expand(
        (
            (video, resolution)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for resolution in (
                [400, 300],
                [640, 480],
                [720, 480],
            )
        ),
        testcase_func_name=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_from_"
            f"{param[0][0]['resolution'][0]}x"
            f"{param[0][0]['resolution'][1]}_to_"
            f"{param[0][1][0]}x{param[0][1][1]}"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_resolution_change(self, video, resolution):
        super().split_and_merge_with_resolution_change(video, resolution)

    @parameterized.expand(
        (
            (video, frame_rate)
            for video in VIDEO_FILES
            for frame_rate in (1, 25, '30000/1001', 60)
        ),
        testcase_func_name=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_of_"
            f"{param[0][0]['video_codec'].value}_"
            f"{param[0][0]['container'].value}_to_"
            f"{str(param[0][1]).replace('/', '_')}_fps"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_frame_rate_change(self, video, frame_rate):
        super().split_and_merge_with_frame_rate_change(video, frame_rate)

    @parameterized.expand(
        (
            (video, subtasks_count)
            for video in VIDEO_FILES  # pylint: disable=undefined-variable
            for subtasks_count in (1, 6, 10, video['key_frames'])
        ),
        name_func=lambda testcase_func, param_num, param: (
            f"{testcase_func.__name__}_{param_num}_of_"
            f"{param[0][0]['video_codec'].value}_"
            f"{param[0][0]['container'].value}_into_"
            f"{param[0][1]}_subtasks"
        ),
    )
    @pytest.mark.slow
    @remove_temporary_dirtree_if_test_passed
    def test_split_and_merge_with_different_subtask_counts(self,
                                                           video,
                                                           subtasks_count):
        super().\
            split_and_merge_with_different_subtask_counts(video, subtasks_count)
