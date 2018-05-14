# Dockerfile for tasks requiring Blender.
# Blender setup is based on
# https://github.com/ikester/blender-docker/blob/master/Dockerfile

FROM golemfactory/base:1.3

MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>

ENV BLENDER_MAJOR=2.79 BLENDER_VERSION=2.79 GLIBC_VERSION=219

RUN set -x \
    && apt-get update \
    && apt-get install -y \
           curl \
           bzip2 \
           libfreetype6 \
           libgl1-mesa-dev \
           libglu1-mesa \
           libxi6 \
           libxrender1 \
    && curl -Ls http://download.blender.org/release/Blender$BLENDER_MAJOR/blender-$BLENDER_VERSION-linux-glibc$GLIBC_VERSION-x86_64.tar.bz2 | tar -xjv -C /opt \
    && ln -s /opt/blender-${BLENDER_VERSION}-linux-glibc${GLIBC_VERSION}-x86_64 /opt/blender \
    && apt-get -y purge curl bzip2 \
    && apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/blender:$PATH
