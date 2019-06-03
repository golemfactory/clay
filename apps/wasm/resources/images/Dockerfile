FROM rust:1.33 as builder
RUN echo "deb http://deb.debian.org/debian stretch-backports main" >> /etc/apt/sources.list
RUN apt -y update && apt -y install autoconf2.13 clang-6.0 --no-install-recommends && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/golemfactory/sp-wasm.git
WORKDIR /sp-wasm
RUN git checkout tags/0.2.1
ENV SHELL=/bin/bash
ENV CC=clang-6.0
ENV CPP="clang-6.0 -E"
ENV CXX=clang++-6.0
RUN cargo install --path /sp-wasm/sp-wasm-cli --root /usr
RUN cargo clean

FROM golemfactory/base:1.5
WORKDIR /
COPY --from=builder /usr/bin/wasm-sandbox /
COPY scripts/ /golem/scripts/
