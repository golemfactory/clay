#!/usr/bin/env bash

output=$(tConvolveCuda)
regex='[0-9]+\.?[0-9]*'
score=$(echo "${output}" | grep "Gridding rate" | grep -oP "${regex}")
echo "${score}"
