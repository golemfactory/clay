# Check if this build can skip slow tests
# Skipping happens when build is a PR with < required approvals
# - input: pull_id from CI ( argv )
# - output: argument to use for this test ( stdout )

import sys
import requests

# input / ouput vars
pull_request_id = sys.argv[1]
run_slow = True

# config vars
required_approvals = 1

# When build is not a PR the input is: "" or "false"
if pull_request_id not in ["", "false"]:
    base_url = "https://api.github.com/" \
        "repos/golemfactory/golem/pulls/{}/reviews"
    url = base_url.format(pull_request_id)

    try:
        # Github API requires user agent.
        req = requests.get(url, headers={'User-Agent': 'build-bot'})

        json_data = req.json()
        key = "state"
        print("{}".format( json_data ), file=sys.stderr)
        result = [a for a in json_data if key in a and a[key] == "APPROVED"]
        approvals = len(result)
        run_slow = approvals >= required_approvals
    except(requests.HTTPError, requests.Timeout) as e:
        sys.stderr.write("Error calling github, run all tests. {}".format(url))

if run_slow:
    # Space in front is important for more arguments later.
    print(" --runslow")
else:
    print("")
