FROM golemfactory/base:1.2

MAINTAINER Jacek Karwowski <jacek@golem.network>

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
RUN apt-get update --fix-missing && apt-get install -y wget bzip2 ca-certificates \
    libglib2.0-0 git

ENV MINICONDA_LINK=https://repo.continuum.io/miniconda/Miniconda3-4.5.4-Linux-x86_64.sh

RUN echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh && \
    wget --quiet ${MINICONDA_LINK} -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh

ENV PATH /opt/conda/bin:$PATH

# Python default pickler doesn't support closures
RUN pip install cloudpickle sklearn numpy hyperopt

# this is a hack to get docker to build
ENV VERSION=11111111111111111111111111111

# This is needed to unpack the data and pack the result
RUN pip install --upgrade git+https://github.com/inexxt/golem_remote.git

# TODO it is temporarly done like that because Golem just runs
# /usr/bin/python in the entrypoint.sh
RUN rm /usr/bin/python && ln -s /opt/conda/bin/python /usr/bin/python