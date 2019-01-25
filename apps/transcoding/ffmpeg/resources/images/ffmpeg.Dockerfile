# Dockerfile for tasks requiring ffmpeg.

FROM golemfactory/base:1.4

MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>

# Build ffmpeg
RUN set -x \
	# get dependencies 
	&& apt-get update  \
	&& apt-get -y install ffmpeg \
	&& apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/* 

RUN /golem/install_py_libs.sh 0 m3u8

COPY ffmpeg-scripts/ /golem/scripts/

ENV PYTHONPATH=/golem/scripts:/golem:$PYTHONPATH

RUN ln -s /usr/bin/python3.6 /usr/bin/python3

WORKDIR /golem/work/
