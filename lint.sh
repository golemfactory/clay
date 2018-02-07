#!/bin/bash
set -e
# a more basic version of lint.sh from marmistrz/lintdiff

BRANCH="origin/develop"
FULL=false
VERBOSE=false
COLUMNS=$(( $(tput cols || echo 80) - 10 ))

hline() {
    printf "%${COLUMNS}s\n" | tr " " "-"
}

usage() {
    printf "Usage: $0 [-b <branch>] [-v] [-h]\n"
    printf "    -b <branch>       branch to use for comparison. default is ${BRANCH}\n"
    printf "    -f                do a full check, not only changed files\n"
    printf "    -v                be verbose\n"
    printf "    -h                show this help message\n"
    exit 1
}

while getopts "b:fvh" opt; do
    case $opt in
        b)
            BRANCH="${OPTARG}"
            ;;
        f)
            FULL=true
            ;;
        v)
            VERBOSE=true
            ;;
        *)
            usage
            ;;
    esac
done

RED=$(
    tput bold
    tput setaf 1
) 2>/dev/null
GREEN=$(
    tput bold
    tput setaf 2
) 2>/dev/null
RESET=$(tput sgr0) 2>/dev/null

nfailed=0

status() {
    if [ "$1" -eq 0 ]; then
        printf " [${GREEN}OK${RESET}]\n"
    else
        printf " [${RED}FAIL${RESET}]\n"
    fi
}

printf "Comparing HEAD..${BRANCH}\n\n"

# credit: https://unix.stackexchange.com/questions/155046/determine-if-git-working-directory-is-clean-from-a-script/183976
if [ -n "$(git status --untracked-files=no --porcelain)" ]; then
  printf "⚡️  You must commit or stash changes.\n"
  exit -1
fi

if [[ "${FULL}" = true ]]; then
    PY_FILES2CHK="apps golem gui scripts setup_util '*.py'"
    PROD_PY_FILES2CHK="${PY_FILES2CHK}"
    TEST_PY_FILES2CHK="tests"
else
    # credit: https://gist.github.com/kentcdodds/9768d9a8d0bfbf6797cd
    PY_FILES2CHK=$(git diff --name-only --diff-filter=d ${BRANCH}..HEAD -- '*.py')

    if [[ -z "${PY_FILES2CHK}" ]]; then
        printf "⚡️  No python files were changed\n"
        exit 0
    elif [[ "${VERBOSE}" = true ]]; then
        printf "Changed python files:\n"
        printf "${PY_FILES2CHK}\n\n" | sed "s/^/    /"
    fi

    PROD_PY_FILES2CHK=$(echo "${PY_FILES2CHK}" | grep -v '^tests/') || true
    TEST_PY_FILES2CHK=$(echo "${PY_FILES2CHK}" | grep '^tests/') || true
fi

LINTDIFF="./lintdiff.sh -o -b ${BRANCH}"

commands=(
    "$LINTDIFF pylint ${PROD_PY_FILES2CHK}"
    "$LINTDIFF pylint --disable=protected-access,no-self-use ${TEST_PY_FILES2CHK}"
    "$LINTDIFF flake8 ${PY_FILES2CHK}"
    "$LINTDIFF mypy ${PY_FILES2CHK}"
)

names=(
    "pylint main"
    "pylint tests"
    "pycodestyle"
    "mypy"
)

for i in "${!names[@]}"; do
    if [[ "${VERBOSE}" = true ]]; then
        printf "%-${COLUMNS}s" "${commands[$i]} ..." | tr '\r\n' ' '
    else
        printf "%-20s" "${names[$i]}..."
    fi
    exitcode[$i]=0
    outputs[$i]=$(${commands[$i]} 2>&1) || exitcode[$i]=$?
    status ${exitcode[$i]}
done

for i in "${!names[@]}"; do
    if [ ${exitcode[$i]} -ne 0 ]; then
        let "nfailed++" || true

        hline
        printf "${names[$i]} failed, output:\n\n"
        printf "${outputs[$i]}\n"
        hline
    fi
done

if [ $nfailed -gt 0 ]; then
    printf "Errors occurred, summary:\n"
    for i in "${!names[@]}"; do
        printf "%-20s" "${names[$i]}..."
        status ${exitcode[$i]}
    done
    exit 1
else
    printf "⚡️  changed files passed linting!\n"
fi
