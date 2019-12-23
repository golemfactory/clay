FROM golemfactory/blender:1.13

# Install scripts requirements first, then add scripts.
ADD entrypoints/scripts/verifier_tools/requirements.txt /golem/work/
ADD entrypoints/scripts/verifier_tools/copy.sh /golem/

# Install any needed packages specified in requirements.txt
RUN set +x \
    && apt-get update \
    && apt-get install -y libglib2.0-0 \
    && apt-get install -y g++ \
    && apt-get install -y libsm6 \
    && apt-get install -y libxrender1 \
    && apt-get install -y wget \
    && apt-get install -y zlib1g-dev \
    && apt-get install -y libopenexr-dev \
    && /golem/install_py_libs.sh /golem/work/requirements.txt \
    && /golem/copy.sh \
    && apt-get remove -y libopenexr-dev \
    && apt-get remove -y zlib1g-dev \
    && apt-get remove -y wget \
    && apt-get remove -y libxrender1 \
    && apt-get remove -y libsm6 \
    && apt-get remove -y g++ \
    && apt-get remove -y libglib2.0-0 \
    && apt-get clean \
    && apt-get -y autoremove \
    && rm -rf /var/lib/apt/lists/*

# Create symbolic link to python. I don't know where, something removes it.
RUN ln -s /usr/bin/python3.6 /usr/bin/python3

ADD entrypoints/scripts/verifier_tools/ /golem/entrypoints/scripts/verifier_tools/
ADD entrypoints/verifier_entrypoint.py /golem/entrypoints/
