#!/bin/bash
# Checks if new lint messages have appeared

REF_BRANCH=origin/develop
CURRENT_BRANCH=$(git symbolic-ref --short -q HEAD)

REF_OUT=/tmp/ref-lint.out
CURRENT_OUT=/tmp/current-lint.out

# get new changes from develop, GitHub doesn't integrate them on its own
echo "Fetching new changes from develop..."
git fetch origin || exit 1

cleanup_artifacts() {
    git reset --hard HEAD
    git checkout "$CURRENT_BRANCH" || exit 1
}
trap cleanup_artifacts EXIT

commit=$(git rev-parse HEAD)
echo "Checking branch $CURRENT_BRANCH, commit: $commit..."
echo "$@"
"$@" > $CURRENT_OUT

git checkout $REF_BRANCH || exit 1
commit=$(git rev-parse HEAD)
# We need to take files responsible for the linting configuration from
# the new commit.
git checkout "$CURRENT_BRANCH" .pylintrc setup.cfg
echo "Checking branch $REF_BRANCH, commit: $commit..."
echo "$@"
"$@" > $REF_OUT

# Remove the trap
trap - EXIT
cleanup_artifacts

diff=$(diff --old-line-format="" --unchanged-line-format="" -w <(sort $REF_OUT) <(sort $CURRENT_OUT))
# There's always a newline, so -gt 1
if [ -n "$diff" ]; then
    echo "New findings!"
    echo "$diff"
    exit 1
else
    echo "Check OK, no new findings..."
fi
