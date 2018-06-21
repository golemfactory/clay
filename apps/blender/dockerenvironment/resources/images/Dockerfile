# Dockerfile for tasks requiring Blender.
# Blender setup is based on
# https://github.com/ikester/blender-docker/blob/master/Dockerfile

FROM golemfactory/base:1.2

MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>

RUN apt-get update && \
	apt-get install -y \
		curl \
		bzip2 \
		libfreetype6 \
		libgl1-mesa-dev \
		libglu1-mesa \
		libxi6 \
		libxrender1 && \
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/*

ENV BLENDER_MAJOR 2.79
ENV BLENDER_VERSION 2.79
ENV GLIBC_VERSION 219
ENV BLENDER_BZ2_URL http://download.blender.org/release/Blender$BLENDER_MAJOR/blender-$BLENDER_VERSION-linux-glibc$GLIBC_VERSION-x86_64.tar.bz2
# ENV BLENDER_BZ2_URL http://mirror.cs.umn.edu/blender.org/release/Blender$BLENDER_MAJOR/blender-$BLENDER_VERSION-linux-glibc211-x86_64.tar.bz2

RUN curl -Ls ${BLENDER_BZ2_URL} | tar -xjv -C /opt && \
    ln -s /opt/blender-${BLENDER_VERSION}-linux-glibc${GLIBC_VERSION}-x86_64 /opt/blender

ENV PATH=/opt/blender:$PATH
