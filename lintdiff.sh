#!/bin/bash
# Checks if new lint messages have appeared

FETCH_ORIGIN=origin
REF_BRANCH=origin/develop
CURRENT_BRANCH=$(git symbolic-ref --short -q HEAD)

REF_OUT=/tmp/ref-lint.out
CURRENT_OUT=/tmp/current-lint.out
FETCH=true

usage() {
    echo "Usage: $0 [-b <branch>] [-o] [-f <origin>] [-h] command"
    echo "    -h                show this help message"
    echo "    -b <branch>       use branch \`branch\` for comparison. Default: origin/develop"
    echo "    -o                offline mode, do not fetch origin"
    echo "    -f <remote>       select the remote to fetch before linting. Default: origin"
    exit 1
}

check_errcode() {
    # Exitcodes >= 126 have special meaning:
    # http://www.tldp.org/LDP/abs/html/exitcodes.html
    if [ "$1" -ge 126 ]; then
        echo "Fatal: command exited with code: $1. Aborting!"
        exit 1
    fi
}

if [ $# -eq 0 ]; then
    usage
fi

while getopts "b:of:h" opt; do
    case $opt in
        b)
            REF_BRANCH=$OPTARG
            ;;
        o)
            FETCH=false
            ;;
        f)
            FETCH_ORIGIN=$OPTARG
            ;;
        *)
            usage
            ;;
    esac
done
shift $((OPTIND - 1))

# get new changes from develop, GitHub doesn't integrate them on its own
if $FETCH; then
    echo "Fetching new changes from develop..."
    git fetch "$FETCH_ORIGIN" || exit 1
fi

cleanup_artifacts() {
    git reset --hard HEAD
    git checkout "$CURRENT_BRANCH" -- || exit 1
}

diff-lines() {
    # Function taken from: https://stackoverflow.com/questions/8259851/using-git-diff-how-can-i-get-added-and-modified-lines-numbers
    # Adjusted the 'echo' line to not print the line content.
    local path=
    local line=
    while read; do
        esc=$'\033'
        if [[ $REPLY =~ ---\ (a/)?.* ]]; then
            continue
        elif [[ $REPLY =~ \+\+\+\ (b/)?([^[:blank:]$esc]+).* ]]; then
            path=${BASH_REMATCH[2]}
        elif [[ $REPLY =~ @@\ -[0-9]+(,[0-9]+)?\ \+([0-9]+)(,[0-9]+)?\ @@.* ]]; then
            line=${BASH_REMATCH[2]}
        elif [[ $REPLY =~ ^($esc\[[0-9;]+m)*([\ +-]) ]]; then
            echo "$path:$line:"
            if [[ ${BASH_REMATCH[2]} != - ]]; then
                ((line++))
            fi
        fi
    done
}

# we checkout the reference branch first in case there are
# uncommitted changes to be overwritten by the merge
git checkout "$REF_BRANCH" -- || exit 1
trap cleanup_artifacts EXIT
commit=$(git rev-parse HEAD)
# We need to take files responsible for the linting configuration from
# the new commit.
git checkout "$CURRENT_BRANCH" -- .pylintrc setup.cfg
echo "Checking branch $REF_BRANCH, commit: $commit..."
echo $@
$@ >$REF_OUT
check_errcode $?

# Now take back the checked out config, go back to the new branch
git reset --hard HEAD
git checkout "$CURRENT_BRANCH" -- || exit 1
# The trap is no longer needed
trap - EXIT
commit=$(git rev-parse HEAD)
echo "Checking branch $CURRENT_BRANCH, commit: $commit..."
echo $@
$@ >$CURRENT_OUT
check_errcode $?

diff=$(diff --old-line-format="" --unchanged-line-format="" -w <(sort $REF_OUT) <(sort $CURRENT_OUT))
if [ -n "$diff" ]; then
    echo -e "New findings:\n"
    echo "$diff"

    # Remove lines from findings based on lines changed
    DIFF_LINES=$(git diff --unified=0 "$REF_BRANCH" "$CURRENT_BRANCH" | diff-lines)
    CHANGED_DIFF=$(echo "$diff" | grep -F "$DIFF_LINES")

    echo -e "\n\nChanged lines findings:\n"
    echo "$CHANGED_DIFF"

    # Remove warning lines starting with W
    CHANGED_ERR=$(echo "$CHANGED_DIFF" | grep -v -e '^W')
    if [ -n "$CHANGED_ERR" ]; then
        exit 1
    fi
else
    echo "Check OK, no new findings..."
fi
