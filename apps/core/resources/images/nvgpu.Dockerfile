# Dockerfile for a base image for computing tasks in Golem.
# Installs python and sets up directories for Golem tasks.

FROM nvidia/cudagl:9.2-runtime

MAINTAINER Marek Franciszkiewicz <marek@golem.network>

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget curl \
    && apt-get install -y python

RUN wget -O /tmp/su-exec "https://github.com/golemfactory/golem/wiki/binaries/su-exec" \
    && test "60e8c3010aaa85f5d919448d082ecdf6e8b75a1c  /tmp/su-exec" = "$(sha1sum /tmp/su-exec)" \
    && mv /tmp/su-exec /usr/local/bin/su-exec \
    && chmod +x /usr/local/bin/su-exec \
    && su-exec nobody true

RUN apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

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
