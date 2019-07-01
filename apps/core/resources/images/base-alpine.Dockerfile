FROM python:3.6-alpine3.8


MAINTAINER Golem Tech <tech@golem.network>


RUN apk add su-exec \
    && which su-exec \
    && su-exec nobody true

RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

COPY core/resources/images/scripts/ /golem/
RUN chmod +x /golem/install_py_libs.sh

WORKDIR /golem/work/

