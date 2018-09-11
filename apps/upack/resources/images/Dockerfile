# Dockerfile for tasks requiring LuxRender.
#list=(180 60 180 300 60 -60); for ((i=0;i<${#list[@]};i++));do line=$(($i+1)); sed -i "${line}s/$/ ${list[$i]}/" cart.in; done
FROM debian:jessie
MAINTAINER Artur Zawłocki <artur.zawlocki@imapp.pl>

ENV PATH="/root/upack/progs:/root/upack/scripts:/home/task/upack/progs:/home/task/upack/scripts:${PATH}"

RUN mkdir /home/task &&\
    apt-get update && \
	apt-get install --no-install-recommends -y \
        apt-utils wget curl ca-certificates \
		curl \
		bzip2 \
        csh \
        tcsh \
        python \
        gfortran \
		libgomp1 && \
    apt-get upgrade -y &&\
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/* &&\
    cd /home/task &&\
    curl ftp://ftp.chem.uu.nl/pub/ks/vaneyck/upack/upack.tar.gz --output upack.tar.gz &&\
    tar xf upack.tar.gz 

RUN wget -O /tmp/su-exec "https://github.com/golemfactory/golem/wiki/binaries/su-exec" \
    && test "60e8c3010aaa85f5d919448d082ecdf6e8b75a1c  /tmp/su-exec" = "$(sha1sum /tmp/su-exec)" \
    && mv /tmp/su-exec /usr/local/bin/su-exec \
    && chmod +x /usr/local/bin/su-exec \
    && su-exec nobody true

RUN cd /home/task/upack/progs && compall

RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i -e 's/\r$//' /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]


