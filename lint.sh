#!/bin/bash
set -e

BRANCH="origin/develop"
FULL=false
VERBOSE=false
COLUMNS=$(( $(tput cols || echo 80) - 10 ))

#credit: https://stackoverflow.com/a/28938235/3805131
RESET='\033[0m' # Text Reset
RED='\033[1;31m' # Bold Red
GREEN='\033[1;32m' # Bold Green

usage() {
    printf "Usage: $0 [-b <branch>] [-v] [-h]\n"
    printf "\nPerforms automatic lint checks for python code; lazy way - only changes\n"
    printf "\nOPTIONS:\n"
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

# to be back compatible
shift $((OPTIND - 1))
[[ -n "$1" ]] && BRANCH="$1"

hline() {
    printf "%${COLUMNS}s\n" | tr " " "-"
}

message() {
    printf "\n⚡️  $1\n\n" >&2
}

status() {
    if [[ "$1" -eq 0 ]]; then
        printf " [${GREEN}OK${RESET}]\n"
    else
        printf " [${RED}FAIL${RESET}]\n"
    fi
}

files_to_check() {
    if [[ "${FULL}" = true ]]; then
        message "Performing full check"
        find . -name '*.py' | cut -f2 -d'/' | uniq
    else
        local cur_hash=$(git rev-parse --short HEAD)
        local ref_hash=$(git rev-parse --short "${BRANCH}")
        message "Comparing HEAD(${cur_hash})..${BRANCH}(${ref_hash})"
        # credit: https://gist.github.com/kentcdodds/9768d9a8d0bfbf6797cd
        git diff --name-only --diff-filter=d "${BRANCH}..HEAD" -- '*.py'
    fi
}

main() {
    # credit: https://unix.stackexchange.com/questions/155046/determine-if-git-working-directory-is-clean-from-a-script/183976
    if [[ -n "$(git status --untracked-files=no --porcelain)" ]]; then
        message "You must commit or stash changes."
        exit -1
    fi

    message "Checking if the requirements are sorted properly"
    ls | grep '^requirements.*txt$' | LC_ALL=C xargs -I@ sort --ignore-case -c @

    files2chk=$(files_to_check)

    if [[ -z "${files2chk}" ]]; then
        message "No python files to check."
        exit 0
    elif [[ "${VERBOSE}" = true ]]; then
        printf "Python files/modules to check:\n" >&2
        printf "${files2chk}\n\n" | sed "s/^/    /"
    fi

    local prod_files2chk=$(printf "${files2chk}" | grep -v '^tests\>' | grep -v '^scripts\>') || true
    local test_files2chk=$(printf "${files2chk}" | grep '^tests\>') || true

    local lintdiff_cmd="./lintdiff.sh -o -b ${BRANCH}"

    local commands=(
        "$lintdiff_cmd pylint ${prod_files2chk}"
        "$lintdiff_cmd pylint --disable=protected-access,no-self-use ${test_files2chk}"
        "$lintdiff_cmd flake8 ${files2chk}"
        "$lintdiff_cmd mypy ${files2chk}"
    )

    local names=(
        "pylint main"
        "pylint tests"
        "pycodestyle"
        "mypy"
    )

    for i in "${!names[@]}"; do
        if [[ "${VERBOSE}" = true ]]; then
            printf "\n${names[$i]}:\n"
            printf "%-${COLUMNS}s" "  ${commands[$i]} ..." | tr '\r\n' ' '
        else
            printf "%-20s" "${names[$i]}..."
        fi
        exitcode[$i]=0
        outputs[$i]=$(${commands[$i]} 2>&1) || exitcode[$i]=$?
        status ${exitcode[$i]}
    done

    local nfailed=0
    for i in "${!names[@]}"; do
        if [[ "${exitcode[$i]}" -ne 0 ]]; then
            let "nfailed++" || true

            hline
            printf "${names[$i]} failed, output:\n\n"
            echo "${outputs[$i]}\n"
            hline
        fi
    done

    if [[ "${nfailed}" -gt 0 ]]; then
        printf "Errors occurred, summary:\n"
        for i in "${!names[@]}"; do
            printf "%-20s" "${names[$i]}..."
            status ${exitcode[$i]}
        done
        exit 1
    else
        message "All checked files passed linting!"
    fi
}

main "$@"
