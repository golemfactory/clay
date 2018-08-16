# Dockerfile for a Golem dummytask .
# Installs python-pip and some python packages

FROM golemfactory/base:1.2

MAINTAINER Jacek Karwowski <jacek@golem.network>

RUN apt-get update
RUN apt-get install python-pip -y
RUN apt-get install python-dev -y

RUN pip install twisted
RUN pip install autobahn
RUN pip install u-msgpack-python
