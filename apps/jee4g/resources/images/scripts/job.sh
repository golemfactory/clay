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

cp -R "${SUBTASK_INPUT_DIR}"/* .
MARKER="${PWD}"/.marker
touch "${MARKER}"

#main execution
${CMD}

#clean up
#find . -type f ! -newer "${MARKER}" | xargs rm -rf 
#rm ${MAKER}

echo ---1
ls -l *
echo ---2
find . -type f ! -newer "${MARKER}" | xargs -I {} echo {} 
find . -type f ! -newer "${MARKER}" | xargs -I {} mv {} ${OUTPUT_DIR}/ 
echo ---3
ls -la ${OUTPUT_DIR}/
echo ---4
rm -rf *
echo ---5
ls -la *
echo ---6
ls -la ${OUTPUT_DIR}/

