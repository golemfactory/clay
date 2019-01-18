# Use an official Python runtime as a parent image
FROM revolutionsystems/python:3.6.3-wee-optimized-lto

# Install any needed packages specified in requirements.txt
RUN apt-get update && apt-get install -y libglib2.0-0 \
    && apt-get install -y libsm6 \
    && apt-get install -y libxrender1 \
    && apt-get install -y wget

RUN mkdir -v /golem \
 && mkdir -v /golem/work \
 && mkdir -v /golem/resources \
 && mkdir -v /golem/output \
 && mkdir -v /golem/scripts

#Get su-exec which will be used to change user id
RUN wget -O /tmp/su-exec "https://github.com/golemfactory/golem/wiki/binaries/su-exec" \
    && test "60e8c3010aaa85f5d919448d082ecdf6e8b75a1c  /tmp/su-exec" = "$(sha1sum /tmp/su-exec)" \
    && mv /tmp/su-exec /usr/local/bin/su-exec \
    && chmod +x /usr/local/bin/su-exec \
    && su-exec nobody true

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i -e 's/\r$//' /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the working directory to /golem/work
WORKDIR /golem/work

# Copy the current directory contents into the container at /golem/work
ADD rendering/resources/images/requirements.txt /golem/work/

ADD rendering/resources/scripts /golem/scripts

RUN pip3 install -r /golem/work/requirements.txt

RUN apt-get clean \
    && apt-get -y autoremove

ENV PYTHONPATH /golem/

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
