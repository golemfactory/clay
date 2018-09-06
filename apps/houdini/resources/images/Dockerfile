# Dockerfile for tasks requiring Houdini.

FROM golemfactory/base:1.2

MAINTAINER Witold Dzięcioł <witek@golem.network>

ADD ./scripts/install /golem/scripts/install

RUN apt-get update && apt-get install python-pip -y && apt-get -y install sudo
RUN pip install beautifulsoup4 requests

ARG AccountName
ARG AccountPassword

RUN exec python /golem/scripts/install/houdini_install.py -u $AccountName -p $AccountPassword -i /opt/houdini

# Install houdini dependencies
RUN apt-get install libpython2.7 -y && \
    apt install libgl1-mesa-glx -y && \
    apt-get install libxmu6 -y && \
    apt-get install libxi6 -y

# Install dependencies used by hkey (license manager)
RUN apt-get install libfontconfig -y && \
    apt-get install libxcursor-dev -y && \
    apt-get install libxcomposite-dev -y && \
    apt-get install libasound2 -y && \
    apt-get install libxtst6 -y && \
    apt-get install libdbus-1-3 -y

ADD ./scripts /golem/scripts
WORKDIR /golem/scripts

RUN pip uninstall beautifulsoup4 requests -y
