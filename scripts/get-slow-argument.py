import sys
import json
import urllib.request;

pullRequestID = sys.argv[1]
runSlow = True

if pullRequestID is not "" and pullRequestID is not "false":
    baseUrl = "https://api.github.com/repos/golemfactory/golem/pulls/{}/reviews"
    url = baseUrl.format(pullRequestID)
    req = urllib.request.Request(url,headers={'User-Agent':'build-bot'})
    with urllib.request.urlopen(req,timeout=10) as f:
        data = f.read().decode('utf-8')

    jsonData = json.loads(data)

    result = [a for a in jsonData if a["state"] is not "APPROVED"]
    approvals = len(result)
    runSlow = approvals >= 2

if runSlow:
    print(" --runslow")
else:
    print("")
