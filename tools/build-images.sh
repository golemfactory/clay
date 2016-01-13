#!/usr/bin/env bash

# Build imapp/blender based on imunes/vroot
docker build -t imapp/blender -f tools/Dockerfile.blender . | tee docker-blender.log

# Build imapp/gnr beased on imapp/blender
docker build -t imapp/gnr -f tools/Dockerfile.gnr . | tee docker-gnr.log
