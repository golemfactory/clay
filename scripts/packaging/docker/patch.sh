#!/bin/bash

if [[ -f "apps/rendering/resources/taskcollector/Makefile" ]]; then
    sed -i "2s/-static/-Bstatic/" "apps/rendering/resources/taskcollector/Makefile"
fi