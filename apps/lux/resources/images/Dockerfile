# Dockerfile for tasks requiring LuxRender.

FROM golemfactory/base:1.2

MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>

RUN apt-get update && \
	apt-get install -y \
		curl \
		bzip2 \
		libglu1-mesa \
		libgomp1 && \
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/*

ENV LUXRENDER_BZ2_URL https://github.com/golemfactory/golem-binary-dependencies/releases/download/luxrender-v1.5.1/lux-v1.5.1-x86_64-sse2.tar.bz2

RUN curl -SL ${LUXRENDER_BZ2_URL} | tar -xjv -C /opt && \
    ln -s /opt/lux-v1.5.1-x86_64-sse2 /opt/luxrender

ENV PATH=/opt/luxrender:$PATH LUXRENDER_ROOT=/opt/luxrender
