# Dockerfile for tasks requiring Houdini.

FROM golemfactory/base:1.2

MAINTAINER Witold Dzięcioł <witek@golem.network>

ADD ./scripts/install /golem/scripts/install

RUN apt-get update && apt-get install python-pip -y && apt-get -y install sudo
RUN pip install beautifulsoup4 requests

RUN exec python /golem/scripts/install/houdini_install.py -u nieznanysprawiciel -p 3F9WbKaHmYdkowzX5zhw -i /opt/houdini

RUN apt-get install libpython2.7 -y && \
    apt install libgl1-mesa-glx -y && \
    apt-get install libxmu6 -y && \
    apt-get install libxi6 -y

ADD ./scripts /golem/scripts
WORKDIR /golem/scripts

RUN pip uninstall beautifulsoup4 requests -y
