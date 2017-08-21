# Check if this build can skip slow tests
# Skipping happens when build is a PR with < 2 approvals
# - input: pull_id from CI ( argv ) 
# - output: argument to use for this test ( stdout )

import sys
import json
import urllib.request;

pullRequestID = sys.argv[1]
runSlow = True

# When build is not a PR the input is: "" or "false"
if pullRequestID not in ["", "false"]:
    baseUrl = "https://api.github.com/repos/golemfactory/golem/pulls/{}/reviews"
    url = baseUrl.format(pullRequestID)
    
    # Github API requires user agent.
    req = urllib.request.Request(url,headers={'User-Agent':'build-bot'})
    with urllib.request.urlopen(req,timeout=10) as f:
        data = f.read().decode('utf-8')

    jsonData = json.loads(data)
    result = [a for a in jsonData if a["state"] is not "APPROVED"]
    approvals = len(result)
    runSlow = approvals >= 2

if runSlow:
    # Space in front is important for more arguments later.
    print(" --runslow")
else:
    print("")
