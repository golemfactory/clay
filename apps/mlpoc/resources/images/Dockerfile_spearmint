# Dockerfile for a base image for computing tasks in Golem.
# Installs python and sets up directories for Golem tasks.

FROM golemfactory/base:1.2

MAINTAINER Jacek Karwowski <jacek@golem.network>


RUN apt-get update --fix-missing && apt-get install -y wget git python-pip python-protobuf python-dev

ENV SPEARMINT_LINK=https://github.com/inexxt/spearmint

RUN cd /opt && \
    git clone ${SPEARMINT_LINK} && \
    cd spearmint && \
    git checkout patch-1

RUN apt-get install -y libblas-dev liblapack-dev liblapacke-dev gfortran && \
	yes | pip install numpy scipy protobuf

ENV PYTHONPATH "/opt/spearmint/spearmint/spearmint:/opt/spearmint/spearmint:/opt/spearmint"

RUN rm /usr/bin/python && ln -s /opt/conda/bin/python /usr/bin/python
