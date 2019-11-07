FROM golemfactory/nvgpu:1.7

# Contents of blender.Dockerfile

MAINTAINER Golem Tech <tech@golem.network>

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


ENV BLENDER_MAJOR 2.80
ENV BLENDER_VERSION 2.80
ENV GLIBC_VERSION 217
ENV BLENDER_BZ2_URL http://download.blender.org/release/Blender$BLENDER_MAJOR/blender-$BLENDER_VERSION-linux-glibc$GLIBC_VERSION-x86_64.tar.bz2
# ENV BLENDER_BZ2_URL http://mirror.cs.umn.edu/blender.org/release/Blender$BLENDER_MAJOR/blender-$BLENDER_VERSION-linux-glibc211-x86_64.tar.bz2

RUN curl -Ls ${BLENDER_BZ2_URL} | tar -xjv -C / && \
    mv /blender-${BLENDER_VERSION}-linux-glibc${GLIBC_VERSION}-x86_64 /blender

RUN /golem/install_py_libs.sh 0 typing

ENV PATH=/blender:/usr/bin/:$PATH

# Create symbolic link to python. I don't know where, something removes it.
RUN ln -s /usr/bin/python3.6 /usr/bin/python3

RUN mkdir -p /golem/entrypoints/scripts
COPY blender/resources/images/entrypoints/scripts/render_tools /golem/entrypoints/scripts/render_tools/
COPY blender/resources/images/entrypoints/render_entrypoint.py /golem/entrypoints/

# NVGPU

ENV CDN_URL https://golem-releases.cdn.golem.network/blender-cycles
ENV BLENDER_DEVICE_TYPE NVIDIA_GPU

RUN curl -OL ${CDN_URL}/filter_sm_62.cubin
RUN curl -OL ${CDN_URL}/kernel_sm_62.cubin
RUN curl -OL ${CDN_URL}/filter_sm_75.cubin
RUN curl -OL ${CDN_URL}/kernel_sm_75.cubin

RUN mv *.cubin /blender/${BLENDER_VERSION}/scripts/addons/cycles/lib
