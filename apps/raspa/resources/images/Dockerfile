# Dockerfile for tasks requiring RASPA.

FROM golemfactory/shell:1.0

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