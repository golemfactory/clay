# Dockerfile for a Golem dummytask .
# Installs python-pip and some python packages

FROM golemfactory/base:1.2

MAINTAINER Jacek Karwowski <jacek@golem.network>

RUN apt-get update
RUN apt-get install python-pip -y
RUN apt-get install python-dev -y

RUN apt-get install libssl-dev -y
RUN apt-get install libffi-dev -y

RUN pip install --upgrade pip
RUN pip install --upgrade setuptools

RUN pip install pyOpenSSL==18.0.0
RUN pip install asn1crypto==0.24.0
RUN pip install attrs==18.1.0
RUN pip install autobahn==18.7.1
RUN pip install Automat==0.7.0
RUN pip install cffi==1.11.5
RUN pip install constantly==15.1.0
RUN pip install cryptography==2.3
RUN pip install enum34==1.1.6
RUN pip install hyperlink==18.0.0
RUN pip install idna==2.7
RUN pip install incremental==17.5.0
RUN pip install ipaddress==1.0.22
RUN pip install pyasn1==0.4.4
RUN pip install pyasn1-modules==0.2.2
RUN pip install pycparser==2.18
RUN pip install PyHamcrest==1.9.0
RUN pip install service-identity==17.0.0
RUN pip install six==1.11.0
RUN pip install Twisted==18.7.0
RUN pip install txaio==18.7.1
RUN pip install u-msgpack-python==2.5.0
RUN pip install zope.interface==4.5.0

