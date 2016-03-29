FROM imapp/blender

MAINTAINER Paweł Bylica <chfast@gmail.com>

# Install python and dependencies for dependencies:
#   python-dev, g++
#   Pillow: libjpeg-dev, zlib1g-dev
#   OpenEXR: libopenexr-dev
#   pycrypto: libgmp-dev
#   ethereum: libssl-dev
RUN apt-get update && apt-get install -y \
    python-pip \
    python-dev \
    g++ dh-autoreconf \
    libjpeg-dev zlib1g-dev libopenexr-dev libgmp-dev libffi-dev \
    libssl-dev ca-certificates \
    pkg-config \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/* \
&& pip install --upgrade pip setuptools cffi \
&& pip install ipfs-api

# Quite stupid, but GNR is not independent yet
COPY . /opt/golem

RUN cd /opt/golem && python setup.py develop

ENV GOLEM=/opt/golem \
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/blender

# use ENTRYPOINT from imunes/vroot:
ENTRYPOINT ["/usr/bin/iinit.sh"]
