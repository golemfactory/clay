# Dockerfile for tasks requiring Houdini.

FROM golemfactory/base:1.2

MAINTAINER Witold Dzięcioł <witek@golem.network>

ADD ./scripts /golem/work

RUN apt-get update && apt-get install python-pip -y && apt-get -y install sudo
RUN pip install beautifulsoup4 requests

RUN exec python ./scripts/houdini_install.py -u nieznanysprawiciel -p 3F9WbKaHmYdkowzX5zhw -i /opt/houdini

WORKDIR /golem/work

RUN pip uninstall beautifulsoup4 requests -y
