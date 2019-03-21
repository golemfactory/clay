# Dockerfile for tasks requiring Blender.
# Blender setup is based on
# https://github.com/ikester/blender-docker/blob/master/Dockerfile

FROM golemfactory/nvgpu:1.2

MAINTAINER Marek Franciszkiewicz <marek@golem.network>

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
ENV CDN_URL https://golem-releases.cdn.golem.network/blender-cycles

RUN curl -Ls ${BLENDER_BZ2_URL} | tar -xjv -C /opt && \
    ln -s /opt/blender-${BLENDER_VERSION}-linux-glibc${GLIBC_VERSION}-x86_64 /opt/blender

RUN curl -OL ${CDN_URL}/filter_sm_62.cubin
RUN curl -OL ${CDN_URL}/kernel_sm_62.cubin
RUN curl -OL ${CDN_URL}/filter_sm_75.cubin
RUN curl -OL ${CDN_URL}/kernel_sm_75.cubin

RUN mv *.cubin /opt/blender/${BLENDER_VERSION}/scripts/addons/cycles/lib

ENV BLENDER_DEVICE_TYPE NVIDIA_GPU
ENV PATH=/opt/blender:$PATH
