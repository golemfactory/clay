#!/bin/bash
# a more basic version of lint.sh from marmistrz/lintdiff

hline() {
    printf %"$COLUMNS"s | tr " " "-"
}

usage() {
    echo "Usage: $0 <reference-branch>"
}

case $# in
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

LINTDIFF="./lintdiff.sh -o -b $BRANCH"

commands=(
    "$LINTDIFF pylint apps golem gui scripts setup_util '*.py'"
    "$LINTDIFF pylint --disable=protected-access,no-self-use tests"
    "$LINTDIFF flake8"
    "$LINTDIFF mypy apps golem gui scripts setup_util tests '*.py'"
)

names=(
    "pylint main"
    "pylint tests"
    "pycodestyle"
    "mypy"
)

cur_hash=$(git rev-parse --short HEAD)
ref_hash=$(git rev-parse --short "$BRANCH")

echo "Comparing $ref_hash...$cur_hash"

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
