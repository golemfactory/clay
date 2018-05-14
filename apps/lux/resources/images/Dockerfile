# Dockerfile for tasks requiring LuxRender.

FROM golemfactory/base:1.3

MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>

RUN set -x \
    && apt-get update \
    && apt-get install -y curl bzip2 libglu1-mesa libgomp1 \
    && curl -SL https://github.com/golemfactory/golem-binary-dependencies/releases/download/luxrender-v1.5.1/lux-v1.5.1-x86_64-sse2.tar.bz2 | tar -xjv -C /opt \
    && ln -s /opt/lux-v1.5.1-x86_64-sse2 /opt/luxrender \
    && apt-get -y purge curl bzip2 \
    && apt-get -y autoremove \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH=/opt/luxrender:$PATH LUXRENDER_ROOT=/opt/luxrender
