# Dockerfile for a base image for computing tasks in Golem.
# Installs python and sets up directories for Golem tasks.

FROM nvidia/cudagl:9.2-runtime

MAINTAINER Marek Franciszkiewicz <marek@golem.network>

ENV VIRTUALGL_VERSION 2.5.1

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget curl \
    && apt-get install -y python

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglu1-mesa-dev mesa-utils xterm && \
    curl -sSL https://downloads.sourceforge.net/project/virtualgl/"${VIRTUALGL_VERSION}"/virtualgl_"${VIRTUALGL_VERSION}"_amd64.deb -o virtualgl_"${VIRTUALGL_VERSION}"_amd64.deb && \
    dpkg -i virtualgl_*_amd64.deb && \
    /opt/VirtualGL/bin/vglserver_config -config +s +f -t && \
    rm virtualgl_*_amd64.deb

RUN wget -O /tmp/su-exec "https://github.com/golemfactory/golem/wiki/binaries/su-exec" \
    && test "60e8c3010aaa85f5d919448d082ecdf6e8b75a1c  /tmp/su-exec" = "$(sha1sum /tmp/su-exec)" \
    && mv /tmp/su-exec /usr/local/bin/su-exec \
    && chmod +x /usr/local/bin/su-exec \
    && su-exec nobody true

RUN apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=$PATH:/opt/VirtualGL/bin
ENV DISPLAY=""
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib:/usr/local/cuda/lib64

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i -e 's/\r$//' /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
