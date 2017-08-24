FROM golemfactory/base:1.2

MAINTAINER Jacek Karwowski <jacek@golem.network>

RUN apt-get update && \
	apt-get install -y \
		curl \
		bzip2 \
		libfreetype6 \
		libgl1-mesa-dev \
		libglu1-mesa \
		libxi6 \
		libxrender1 && \
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/*

ENV MINICONDA_URL https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh

RUN echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh && \
    wget --quiet ${MINICONDA_URL} -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh

ENV PATH=/opt/conda/bin:$PATH

RUN conda install -y pytorch -c soumith
RUN conda install -y dill