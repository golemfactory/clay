#!/bin/sh

docker build -t golem/pack -f docker/Dockerfile.pack docker
docker run -it -v /tmp:/tmp golem/pack
