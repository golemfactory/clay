# CUDA benchmark: pts/askap-1.0.0 - 10 November 2015 - ASKAP CUDA test
FROM nvidia/cudagl:9.2-devel-ubuntu18.04 AS CUDA-DEVEL

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib:/usr/local/cuda/lib64

RUN apt-get update
RUN apt-get install -y wget
RUN wget http://www.phoronix-test-suite.com/benchmark-files/askap-benchmarks-20151110.tar.gz
RUN tar -zxf askap-benchmarks-20151110.tar.gz
RUN cd askap-benchmarks/tConvolveCuda && make

RUN cp askap-benchmarks/tConvolveCuda/tConvolveCuda /usr/local/bin/


# golemfactory/gpu_benchmark
FROM nvidia/cudagl:9.2-runtime-ubuntu18.04
MAINTAINER Golem Tech <tech@golem.network>

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/cuda/lib:/usr/local/cuda/lib64

RUN apt-get update
RUN apt-get install -y libglu1-mesa freeglut3 gawk
RUN apt-get clean && apt-get -y autoremove

COPY --from=CUDA-DEVEL /usr/local/bin/tConvolveCuda /usr/local/bin/
COPY benchmark.sh /usr/local/bin/

ENTRYPOINT ["/bin/bash", "/usr/local/bin/benchmark.sh"]
