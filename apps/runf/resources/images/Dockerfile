FROM golemfactory/base:1.2

MAINTAINER Jacek Karwowski <jacek@golem.network>

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8
RUN apt-get update --fix-missing && apt-get install -y wget bzip2 ca-certificates \
    libglib2.0-0 git

ENV MINICONDA_LINK=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh

RUN echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh && \
    wget --quiet ${MINICONDA_LINK} -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh

ENV PATH /opt/conda/bin:$PATH

RUN pip install cloudpickle
RUN pip install git+https://github.com/inexxt/golem_remote.git
RUN rm /usr/bin/python && ln -s /opt/conda/bin/python /usr/bin/python