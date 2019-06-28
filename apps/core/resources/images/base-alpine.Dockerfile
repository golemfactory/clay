FROM python:3.6-alpine3.8


MAINTAINER Golem Tech <tech@golem.network>


RUN apk add su-exec \
    && which su-exec \
    && su-exec nobody true

RUN mkdir /golem \
 && mkdir /golem/work \
 && mkdir /golem/resources \
 && mkdir /golem/output

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i -e 's/\r$//' /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

COPY core/resources/images/scripts/ /golem/
RUN chmod +x /golem/install_py_libs.sh

WORKDIR /golem/work/

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
