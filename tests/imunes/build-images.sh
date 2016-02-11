#!/usr/bin/env bash

DOCKERFILE_DIR=`dirname $0`

# Build imapp/blender based on imunes/vroot
docker build -t imapp/blender -f ${DOCKERFILE_DIR}/Dockerfile.blender . | tee docker-blender.log

# Build imapp/gnr beased on imapp/blender
docker build -t imapp/gnr -f ${DOCKERFILE_DIR}/Dockerfile.gnr . | tee docker-gnr.log
