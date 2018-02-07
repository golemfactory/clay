#!/bin/bash
set -e
# a more basic version of lint.sh from marmistrz/lintdiff

BRANCH="origin/develop"
VERBOSE=false
COLUMNS=$(( $(tput cols) - 10 ))

hline() {
    printf "%${COLUMNS}s\n" | tr " " "-"
}

usage() {
    printf "Usage: $0 [-b <branch>] [-v] [-h]\n"
    printf "    -b <branch>       branch to use for comparison. default is ${BRANCH}\n"
    printf "    -v                be verbose\n"
    printf "    -h                show this help message\n"
    exit 1
}

while getopts "b:vh" opt; do
    case $opt in
        b)
            BRANCH="${OPTARG}"
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

# credit: https://gist.github.com/kentcdodds/9768d9a8d0bfbf6797cd
CHG_PY_FILES=$(git diff --name-only --diff-filter=d ${BRANCH}..HEAD -- '*.py')

if [[ -z "${CHG_PY_FILES}" ]]; then
    printf "⚡️  No python files were changed\n"
    exit 0
elif [[ "${VERBOSE}" = true ]]; then
    printf "Changed python files:\n"
    printf "${CHG_PY_FILES}\n\n" | sed "s/^/    /"
fi

CHG_PY_PROD_FILES=$(echo "${CHG_PY_FILES}" | grep -v '^tests/') || true
CHG_PY_TEST_FILES=$(echo "${CHG_PY_FILES}" | grep '^tests/') || true

LINTDIFF="./lintdiff.sh -o -b ${BRANCH}"

commands=(
    "$LINTDIFF pylint ${CHG_PY_PROD_FILES}"
    "$LINTDIFF pylint --disable=protected-access,no-self-use ${CHG_PY_TEST_FILES}"
    "$LINTDIFF flake8 ${CHG_PY_FILES}"
    "$LINTDIFF mypy ${CHG_PY_FILES}"
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
