# Dockerfile for a base image for computing tasks in Golem.
# Installs python and sets up directories for Golem tasks.

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

RUN conda install pytorch cuda80 -c soumith
ENV NO_CUDA=1

RUN conda install dill pandas scikit-learn

RUN rm /usr/bin/python && ln -s /opt/conda/bin/python /usr/bin/python
