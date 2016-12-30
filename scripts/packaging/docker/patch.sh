#!/bin/bash

TC_MAKEFILE="apps/rendering/resources/taskcollector/Makefile"

if [[ -f "$TC_MAKEFILE" ]]; then
    sed -i "2s/-static/-Bstatic/" "$TC_MAKEFILE"
fi