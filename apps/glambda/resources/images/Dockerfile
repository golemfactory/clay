# Dockerfile for a base image for computing tasks in Golem.
# Installs python and sets up directories for Golem tasks.

FROM ubuntu:18.04

RUN set -x \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates wget curl pkg-config libopenbabel-dev swig \
    && apt-get install -y python3 python3-pip

RUN set -x \
    && pip3 install cloudpickle==0.6.1 RASPA2 openbabel

RUN wget -O /tmp/su-exec "https://github.com/golemfactory/golem/wiki/binaries/su-exec" \
    && test "60e8c3010aaa85f5d919448d082ecdf6e8b75a1c  /tmp/su-exec" = "$(sha1sum /tmp/su-exec)" \
    && mv /tmp/su-exec /usr/local/bin/su-exec \
    && chmod +x /usr/local/bin/su-exec \
    && su-exec nobody true

RUN apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i -e 's/\r$//' /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

ENV RASPA_DIR=/opt/RASPA

RUN mkdir /golem/raspa && \
    apt-get update && \
	apt-get install -y \
        apt-utils \
		curl \
		bzip2 \
        git \
        libtool \
        automake \
        make \
		libglu1-mesa \
		libgomp1 && \
    apt-get upgrade -y && \
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/* && \
    git clone https://github.com/numat/RASPA2.git && \
    cd RASPA2 && \
    mkdir m4 && \
    aclocal && \
    autoreconf -i && \
    automake --add-missing && \
    autoconf && \
    ./configure --prefix=${RASPA_DIR} && \
    make  -j8 && \
    make install && \
    chmod -R 757 ${RASPA_DIR}

RUN mkdir -p /golem/scripts
COPY glambda/resources/scripts/job.py /golem/scripts/job.py
