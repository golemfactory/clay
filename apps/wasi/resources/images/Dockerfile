FROM rust:1.34 as builder
RUN echo "deb http://deb.debian.org/debian stretch-backports main" >> /etc/apt/sources.list
RUN apt -y update && apt -y install cmake clang-6.0 --no-install-recommends && rm -rf /var/lib/apt/lists/*

RUN git clone --recurse-submodules https://github.com/kubkon/wasmtime.git
WORKDIR /wasmtime
ENV SHELL=/bin/bash
ENV CC=clang-6.0
ENV CPP="clang-6.0 -E"
ENV CXX=clang++-6.0
RUN cargo install --path . --root /usr
RUN cargo clean

FROM golemfactory/base:1.4
WORKDIR /
COPY --from=builder /usr/bin/wasmtime /
COPY scripts/ /golem/scripts/
RUN apt -y update && apt -y install python3-pip
