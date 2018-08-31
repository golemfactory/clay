#!/bin/bash

houdini_setup_dir=$1
task_definition_file=$2

prev_working_dir=$PWD

cd $houdini_setup_dir
source houdini_setup_bash
cd $prev_working_dir

python houdini_render.py $task_definition_file
