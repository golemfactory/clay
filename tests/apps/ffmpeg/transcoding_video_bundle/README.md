## Transcoding video bundle

This directory contains scripts for building the set of videos used by Golem's transcoding tests.

If you just want to run the tests, use `download-bundle.sh` to get a prebuilt bundle from the sever.

### Downloading a prebuilt bundle
Just run:
``` bash
./download-bundle.sh
```

That's all.
It downloads the package from the URL hard-coded in the file, unpacks it into the directory where the transcoding tests look for videos and then deletes the archive.

### Building a bundle from scratch

#### Prerequisites
- Linux (should work on Mac OS too but it was not tested in that environment)
- Bash
- FFmpeg
- curl
- zip/unzip
- Python 3

#### Usage
Just run `build.sh` giving it a version for the new bundle:
``` bash
./build.sh 4
```

A version can be anything but an integer is recommended.
The current version is hard-coded in `download-bundle.sh`.

This will:
- Download the videos listed in `video-sources.txt` into `transcoding-video-bundle/download/`.
- Analyze every video using ffprobe and automatically build a file name that includes the most important parameters.

    Example:
    ```
    matroska-test5[h264+aac+aac,1024x576,47s,v1a2s0d8,i1149p1655b1609,24fps].mkv
    ```
    - `matroska` - short, unique identifier for the source/site the video came from (from `video-sources.txt`)
    - `test5` - short, unique identifier for a specific video (from `video-sources.txt`)
    - `h264+aac+aac` - video and audio codecs
    - `1024x576` - video resolutikon
    - `47s` - duration
    - `v1a2s0d8` - numbers of video, audio, subtitle and data streams
    - `i1149p1655b1609` - numbers of I-, P- and B-frames
    - `23.976fps` - frame rate
- Move the renamed videos to `transcoding-video-bundle/original/`.
- Split every video longer than the duration specified in `video-sources.txt` into shorter segments and select one segment for use in tests.
    - The segment gets a suffix like `[segment1of10]` to distinguish it from the original.
        Note that parameters in the name are not updated.
        In particular the duration still comes from the original video.
    - If the duration in `video-sources.txt` is an integer, the file (or the segment if there was a split) is copied to `transcoding-video-bundle/good/`.
    - If the duration is set to `bad` rather than an integer, it indicates that we determined that ffmpeg has problems dealing with the file.
      It may be damaged or simply unsupported.
      We still want to test with such files so the file is preserved but it's never split and goes to `transcoding-video-bundle/bad/`.
- Create `transcoding-video-bundle/index.md` which contains a Markdown table listing the renamed files and the URLs they originally came from.
- Create two .zip files:
    - `transcoding-video-bundle-v4.zip` containing `bad/` and `good/` - the files meant to be used in tests.
    - `transcoding-video-bundle-v4-original.zip` containing `original/` - the original files from before split in case they become unavailable from the original source.

Once the packages are ready, you can inspect `transcoding-video-bundle/` to make sure that the content is not broken and then remove it.
