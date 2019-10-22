
# Stats builder from golemfactory/base
FROM golang:alpine as stats-builder
ENV CGO_ENABLED=0
RUN apk add --no-cache git gcc musl-dev openssl ca-certificates
RUN git clone --depth 1 --branch 0.1 https://github.com/golemfactory/docker-cgroups-stats.git /build
WORKDIR /build
RUN go build -o docker-cgroups-stats main.go


# Dockerfile with ffmpeg and python3.6

# From this image we will copy ffmpeg binaries.
FROM jrottenberg/ffmpeg:4.1-alpine AS ffmpeg-build


# Base image with alpine and python.
FROM python:3.6-alpine3.8

MAINTAINER Golem Tech <tech@golem.network>

# Create Golem standard directories.
RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

# Copy stats builder
RUN apk add ca-certificates
COPY --from=stats-builder /build/docker-cgroups-stats /usr/bin


COPY ffmpeg-scripts/requirements.txt /golem/scripts/requirements.txt
RUN pip install -r /golem/scripts/requirements.txt

COPY ffmpeg-scripts/ /golem/scripts/

ENV PYTHONPATH=/golem/scripts:/golem:$PYTHONPATH

WORKDIR /golem/work/

# Copy ffmpeg bianries from jrottenberg/ffmpeg:4.1-alpine image.
COPY --from=ffmpeg-build /usr/local /usr/local
COPY --from=ffmpeg-build /usr/lib /usr/lib
COPY --from=ffmpeg-build /lib /lib

#ENTRYPOINT []
