# Dockerfile for a base image for computing tasks in Golem.
# Installs python and sets up directories for Golem tasks.

FROM ubuntu:18.04

MAINTAINER Golem Tech <tech@golem.network>

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && apt-get install -y python3.6 \
    && apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3.6 /usr/bin/python3

RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

COPY core/resources/images/scripts/ /golem/
RUN chmod +x /golem/install_py_libs.sh

WORKDIR /golem/work/
