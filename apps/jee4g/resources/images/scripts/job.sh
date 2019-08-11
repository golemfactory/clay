#!/bin/sh

INPUT_DIR=${RESOURCES_DIR}/`jq -r '.input_dir_name' params.json`
JAR=${INPUT_DIR}/`jq -r '.jar_name' params.json`
SUBTASK_INPUT_DIR=${INPUT_DIR}/`jq -r '.name' params.json`

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
if [ ! printf "$JAR" | grep -Eq "$T" ]; then
	printf "invalid JAR name\n";
	printf "--""${JAR}""---"
	printf "\n"
	printf "$JAR" | grep -Eq "$T"
        exit 2;
fi

#jq uses newlines as separator
EXEC_ARGS=`jq -r '.exec_args[]' params.json`
IFS="
"
CMD="java
-Djava.security.manager
-Djava.security.policy=/home/lukaszglen/java_test_1/scripts/jee4g.policy
-jar
${JAR}
${EXEC_ARGS}"

cp -R "${SUBTASK_INPUT_DIR}"/* "${OUTPUT_DIR}"
MARKER="${PWD}"/.marker
touch "${MARKER}"

#we need to change working directory because of security policy
cd "${OUTPUT_DIR}"

#main execution
${CMD}

#clean up
find "${OUTPUT_DIR}" -type f ! -newer "${MARKER}" | xargs rm -rf 
rm ${MARKER}

