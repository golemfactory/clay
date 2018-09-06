#!/bin/bash

houdini_setup_dir=$1
task_definition_file=$2

prev_working_dir=$PWD

cd $houdini_setup_dir
source houdini_setup_bash
cd $prev_working_dir


cp /golem/work/licenses /usr/lib/sesi/licenses

echo "-V 4 -z 1048576 -l /golem/work/logs/sesinetd.log -u /golem/work/logs/sesinetd-licenses.log" > /usr/lib/sesi/sesinetd.options
/etc/init.d/sesinetd start

python houdini_render.py $task_definition_file
