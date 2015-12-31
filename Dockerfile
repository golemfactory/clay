FROM ikester/blender

MAINTAINER Paweł Bylica <chfast@gmail.com>

# Install python and dependencies for dependencies:
#   python-dev, g++
#   Pillow: libjpeg-dev, zlib1g-dev
#   OpenEXR: libopenexr-dev
#   pycrypto: libgmp-dev
#   ethereum: libssl-dev
RUN apt-get update && apt-get install -y \
    python-setuptools \
    python-dev \
    g++ dh-autoreconf \
    libjpeg-dev zlib1g-dev libopenexr-dev libgmp-dev libffi-dev \
    libssl-dev \
    wget \
&& apt-get clean \
&& rm -rf /var/lib/apt/lists/*

RUN wget https://bootstrap.pypa.io/ez_setup.py -O - | python

# Quite stupid, but GNR is not independent yet
COPY . /opt/golem

ENV GOLEM=/opt/golem PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/blender:/usr/bin/luxrender
ENV PYTHONPATH=$GOLEM

RUN cd /opt/golem && libtoolize && python setup.py install

RUN cd /tmp && wget http://www.luxrender.net/release/luxrender/1.5/linux/lux-v1.5.1-x86_64-sse2.tar.bz2 && tar jxf lux-v1.5.1-x86_64-sse2.tar.bz2 && mv lux-v1.5.1-x86_64-sse2 /usr/bin/luxrender
ENV LUXRENDER_ROOT=/usr/bin/luxrender

WORKDIR /opt/golem/

ENTRYPOINT ["/usr/bin/python", "gnr/node.py"]