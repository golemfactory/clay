#!/bin/bash
# a more basic version of lint.sh from marmistrz/lintdiff

DEFAULT_BRANCH="origin/develop"

hline() {
    printf %"$COLUMNS"s | tr " " "-"
}

usage() {
    echo "Usage: $0 <reference-branch>"
    echo "default reference branch is ${DEFAULT_BRANCH}"
}

case $# in
    0)
        BRANCH="${DEFAULT_BRANCH}"
        echo "Using ${DEFAULT_BRANCH} as reference branch"
        ;;
    1)
        if [ "$1" == "-h" ]; then
            usage
            exit 0
        else
            BRANCH="$1"
        fi
        ;;
    *)
        usage
        exit 1
        ;;
esac

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
        echo "${GREEN}OK${RESET}"
    else
        echo "${RED}FAIL${RESET}"
    fi
}

CUR_HASH=$(git rev-parse --short HEAD)
REF_HASH=$(git rev-parse --short "${BRANCH}")

echo "Comparing ${REF_HASH}...${CUR_HASH}"

changed_files() {
    git diff --name-only "${CUR_HASH}..${REF_HASH}" | grep '\.py$'
}

changed_prod_files() {
    changed_files | grep -v '^tests/'
}

changed_test_files() {
    changed_files | grep '^tests/'
}


LINTDIFF="./lintdiff.sh -o -b ${BRANCH}"

commands=(
    "$LINTDIFF pylint $(changed_prod_files)"
    "$LINTDIFF pylint --disable=protected-access,no-self-use $(changed_test_files)"
    "$LINTDIFF flake8 $(changed_files)"
    "$LINTDIFF mypy $(changed_files)"
)

names=(
    "pylint main"
    "pylint tests"
    "pycodestyle"
    "mypy"
)

for i in "${!names[@]}"; do
    printf "%-20s" "${names[$i]}..."
    outputs[$i]=$(${commands[$i]} 2>&1)
    exitcode[$i]=$?
    status ${exitcode[$i]}
done

for i in "${!names[@]}"; do
    if [ ${exitcode[$i]} -ne 0 ]; then
        let "nfailed++"

        hline
        echo "${names[$i]} failed, output:"
        echo -e "\n"
        echo "${outputs[$i]}"
        hline
    fi
done

if [ $nfailed -gt 0 ]; then
    echo "Errors occurred, summary:"
    for i in "${!names[@]}"; do
        printf "%-20s" "${names[$i]}..."
        status ${exitcode[$i]}
    done
    exit 1
fi
