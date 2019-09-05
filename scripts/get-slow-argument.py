# Check if this build can skip slow tests
# Skipping happens when build is a PR with < required approvals
# - input: pull_id from CI ( argv )
# - output: argument to use for this test ( stdout )

import os
import sys
import requests

# input / ouput vars
pull_request_id = sys.argv[1]
run_slow = True

# config vars
required_approvals = 1

_logging = os.environ.get('LOGGING', False)


class ApprovalError(Exception):
    pass


def _log(msg, *args):
    if _logging:
        sys.stderr.write(msg.format(*args) + '\n')


def _get_json_data(link):
    _log("_get_json_data: {}", link)
    # Github API requires user agent.
    req = requests.get(url, headers={'User-Agent': 'build-bot'})
    json_data = req.json()

    if "message" in json_data \
            and json_data["message"].startswith("API rate"):

        sys.stderr.write("Raw reply:{}".format(json_data))
        raise ApprovalError

    return req, json_data


# When build is not a PR the input is: "" or "false"
if pull_request_id not in ["", "false"]:
    base_url = "https://api.github.com/" \
        "repos/golemfactory/golem/pulls/{}/reviews"
    url = base_url.format(pull_request_id)

    try:
        req, json_data = _get_json_data(url)

        while 'next' in req.links:
            _log("got link: {}", req.links)
            url = req.links['next']['url']
            req, new_json_data = _get_json_data(url)
            json_data += new_json_data

        # _log("Raw json_data: {}", json_data)
        _log("len json_data: {}", len(json_data))

        check_states = ["APPROVED", "CHANGES_REQUESTED"]
        review_states = [a for a in json_data if a["state"] in check_states]
        unique_reviews = {x['user']['login']: x for x in review_states}.values()
        _log("unique_reviews: {}", unique_reviews)

        result = [a for a in unique_reviews if a["state"] == "APPROVED"]
        _log("result: {}", result)
        approvals = len(result)
        _log("approvals: {}", approvals)
        run_slow = approvals >= required_approvals
    except(requests.HTTPError, requests.Timeout, ApprovalError) as e:
        sys.stderr.write("Error calling github, run all tests. {}".format(url))

if run_slow:
    # Space in front is important for more arguments later.
    print(" --runslow")
else:
    print("")
