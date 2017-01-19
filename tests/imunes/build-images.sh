#!/usr/bin/env bash

DOCKERFILE_DIR=`dirname $0`

# Build imapp/blender based on imunes/vroot
docker build -t imapp/blender -f ${DOCKERFILE_DIR}/Dockerfile.blender . | tee docker-blender.log

# Build imapp/core beased on imapp/blender
docker build -t imapp/core -f ${DOCKERFILE_DIR}/Dockerfile.core . | tee docker-core.log
