# Use an official Python runtime as a parent image
FROM revolutionsystems/python:3.6.3-wee-optimized-lto

# Install any needed packages specified in requirements.txt
RUN apt-get update && apt-get install -y libglib2.0-0 \
    && apt-get install -y libsm6 \
    && apt-get install -y libxrender1

RUN mkdir -v /golem \
 && mkdir -v /golem/work \
 && mkdir -v /golem/resources \
 && mkdir -v /golem/output \
 && mkdir -v /golem/scripts

# Set the working directory to /golem/work
WORKDIR /golem/work

# Copy the current directory contents into the container at /golem/work
ADD requirements.txt /golem/work/

ADD scripts /golem/scripts

RUN pip3 install -r /golem/work/requirements.txt

RUN apt-get clean \
    && apt-get -y autoremove

ENV PYTHONPATH /golem/

ENTRYPOINT ["python3", "job.py"]