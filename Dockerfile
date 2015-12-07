FROM ikester/blender

MAINTAINER Paweł Bylica <chfast@gmail.com>

# Install python and dependencies for dependencies:
#   python-dev, g++
#   Pillow: libjpeg-dev, zlib1g-dev
#   OpenEXR: libopenexr-dev
#   pycrypto: libgmp-dev
RUN apt-get update && apt-get install -y \
    python-setuptools \
    python-dev \
    g++ dh-autoreconf \
    libjpeg-dev zlib1g-dev libopenexr-dev libgmp-dev libffi-dev \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*


# Quite stupid, but GNR is not independent yet
COPY . /opt/golem

RUN cd /opt/golem && python setup.py install

ENV GOLEM=/opt/golem PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/blender

WORKDIR /opt/golem/examples/gnr

ENTRYPOINT ["/usr/bin/python", "node.py"]
