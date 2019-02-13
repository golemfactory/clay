FROM golemfactory/blender_verifier:1.0

RUN /golem/install_py_libs.sh 0 click
RUN ln -s /usr/bin/python3.6 /usr/bin/python3

ENV LC_ALL C.UTF-8
ENV LANG C.UTF-8

WORKDIR /work

# RUN apt-get update && apt-get install -y build-essential libfreeimage-dev
# COPY taskcollector /golem/taskcollector
# RUN make -C /golem/taskcollector

COPY benchmark /golem/benchmark

COPY commands /golem/commands

ENTRYPOINT ["/usr/local/bin/entrypoint.sh", "python3", "/golem/commands/entrypoint.py"]