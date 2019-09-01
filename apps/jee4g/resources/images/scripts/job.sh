#!/bin/sh

INPUT_DIR=${RESOURCES_DIR}
INPUT_DIR_NAME=`jq -r '.input_dir_name' params.json`
if [ ! -z ${INPUT_DIR_NAME} ]; then
        INPUT_DIR=${INPUT_DIR}/${INPUT_DIR_NAME}
fi
JAR=${INPUT_DIR}/`jq -r '.jar_name' params.json`
SUBTASK_INPUT_DIR=${INPUT_DIR}/`jq -r '.name' params.json`

#cat params.json
#ls -l ${RESOURCES_DIR}
#ls -l ${OUTPUT_DIR}

if [ ! -d "${OUTPUT_DIR}" ]; then
	printf "OUTPUT_DIR is not a directory\n";
	exit 1;
fi
if [ ! -d "${SUBTASK_INPUT_DIR}" ]; then
	printf "subtask INPUT_DIR (SUBTASK_INPUT_DIR) is not a directory\n";
        exit 1;
fi


#we do not want names to contain new lines, because newlines are separators for exec
T="
"
if [ ! -z `printf "$JAR" | grep "$T"`]; then
	printf "invalid JAR name\n";
	printf "--""${JAR}""---"
        exit 2;
fi

#jq uses newlines as separator
EXEC_ARGS=`jq -r '.exec_args[]' params.json`
IFS="
"

#path to security policy is hardcoded :(, so we check
if [ ! -f "/golem/scripts/jee4g.policy" ]; then
	printf "missing security policy file /golem/scripts/jee4g.policy\n"
	exit 3;
fi

CMD="java
-Djava.security.manager
-Djava.security.policy=/golem/scripts/jee4g.policy
-jar
${JAR}
${EXEC_ARGS}"

MARKER="${PWD}"/.marker
touch "${MARKER}"

JEE4G_WORKING_DIR=jee4g_working_dir
mkdir ${JEE4G_WORKING_DIR}
cd ${JEE4G_WORKING_DIR}
cp -R "${SUBTASK_INPUT_DIR}"/* .

#main execution
${CMD}

#clean up
find . -type f ! -newer "${MARKER}" | xargs -I {} mv {} ${OUTPUT_DIR}/
cd ..
rm -rf ${JEE4G_WORKING_DIR}
rm "${MARKER}"

