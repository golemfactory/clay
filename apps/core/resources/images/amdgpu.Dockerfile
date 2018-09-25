FROM golemfactory/base:1.2

MAINTAINER Marek Franciszkiewicz <marek@golem.network>

ENV AMD_LIB amdgpu_lib.tar.gz
ENV AMD_ETC amdgpu_etc.tar.gz

ADD $AMD_LIB /opt
ADD $AMD_ETC /etc

RUN ldconfig /usr/lib /opt/amdgpu/lib/x86_64-linux-gnu
