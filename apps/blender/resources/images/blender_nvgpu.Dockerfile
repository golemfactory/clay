# Dockerfile for tasks requiring Blender.
# Blender setup is based on
# https://github.com/ikester/blender-docker/blob/master/Dockerfile

FROM golemfactory/nvgpu:1.2

MAINTAINER Golem Tech <tech@golem.network>

FROM golemfactory/blender:1.8

ENV BLENDER_DEVICE_TYPE NVIDIA_GPU
