# Dockerfile for a base image for computing tasks in Golem.
# It compiles and installs Python 3, sets up directories for Golem tasks and downloads su-exec.
# Since this image uses the "multi-stage builds" feature, it must be build by Docker 17.05 or higher.

FROM debian:jessie as python3_builder
ENV PYTHON_VERSION=3.6.5
RUN set -x \
    && apt-get update \
    && apt-get install -y ca-certificates wget tcl tk build-essential dpkg-dev tcl-dev tk-dev --no-install-recommends \
    && wget -O python.tar.xz "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz" \
    && wget -O python.tar.xz.asc "https://www.python.org/ftp/python/${PYTHON_VERSION%%[a-z]*}/Python-$PYTHON_VERSION.tar.xz.asc" \
    && export GNUPGHOME="$(mktemp -d)" \
    && gpg --keyserver ha.pool.sks-keyservers.net --recv-keys "0D96DF4D4110E5C43FBFB17F2D347EA6AA65421D" \
    && gpg --batch --verify python.tar.xz.asc python.tar.xz \
    && mkdir -p /usr/src/python \
    && tar -xJC /usr/src/python --strip-components=1 -f python.tar.xz \
    && cd /usr/src/python \
    && gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)" \
    && ./configure \
         --build="$gnuArch" \
         --enable-shared \
         --with-system-expat \
         --with-system-ffi \
         --without-ensurepip \
    && make -j "$(nproc)" \
    && make install \
    && ldconfig \
    && find /usr/local -depth \
       \( \
         \( -type d -a \( -name test -o -name tests -o -name turtledemo -o -name config-3.6m-x86_64-linux-gnu -o -name ensurepip \) \) -o \( -type f -a \( -name '*.pyc' -o -name '*.pyo' \) \) \
       \) -exec rm -rf '{}' +

FROM python3_builder as export_files_collector
COPY entrypoint.sh /tmp/entrypoint.sh
RUN set -x \
    && mkdir /export_files \
    && cp -r /usr/local/bin /export_files \
    && cp -r /usr/local/lib /export_files \
    && cp -r /usr/local/share /export_files \
    && mv /tmp/entrypoint.sh /export_files/bin \
    && sed -i -e 's/\r$//' /export_files/bin/entrypoint.sh \
    && chmod +x /export_files/bin/entrypoint.sh \
    && wget -O /export_files/bin/su-exec "https://github.com/golemfactory/golem/wiki/binaries/su-exec" \
    && test "60e8c3010aaa85f5d919448d082ecdf6e8b75a1c  /export_files/bin/su-exec" = "$(sha1sum /export_files/bin/su-exec)" \
    && chmod +x /export_files/bin/su-exec

FROM debian:jessie
MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>
COPY --from=export_files_collector /export_files /usr/local/
RUN set -x \
    && su-exec nobody true \
    && ldconfig \
    && mkdir /golem \
    && mkdir /golem/work \
    && mkdir /golem/resources \
    && mkdir /golem/output

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
