from __future__ import print_function

import imp
import os
import sys

import params  # This module is generated before this script is run

OUTPUT_DIR = "/golem/output"
WORK_DIR = "/golem/work"  # we don't need that, all the work is done in memory
RESOURCES_DIR = "/golem/resources"


def run(data_files, subtask_data, difficulty, result_size, result_file):
    code_file = os.path.join(RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)

    data_file = os.path.join(RESOURCES_DIR, "data", data_files[0])
    result_path = os.path.join(OUTPUT_DIR, result_file)

    solution = computing.run_dummy_task(data_file,
                                        subtask_data,
                                        difficulty,
                                        result_size)

    # TODO try catch and log errors. Issue #2425
    with open(result_path, "w") as f:
        f.write("{}".format(solution))


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)


# We don't send messages if the task is run in LocalComputer
if not hasattr(params, "FLAGS") or \
   not "MESSAGES_AVAILABLE" in params.FLAGS or \
   not params.FLAGS["MESSAGES_AVAILABLE"]:
    print("Messages not available")
    sys.exit(0)
else:
    print("Messages available")

# -------------------------------------------------------------------
# Dummy messages
#####################################################################

state_update_info = {u"task_id": params.task_id.decode("utf-8"),
                     u"subtask_id": params.subtask_id.decode("utf-8"),
                     u"state_update_id": u"1"}
message = {
    u"info": state_update_info,
    u"data": {u"aa": u"bb"}
}


USER = params.user
SECRET = params.secret
URL = u"wss://172.17.0.1:61000"
REALM = u"golem"

X509_COMMON_NAME = u"golem.local"

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
from twisted.internet._sslverify import optionsForClientTLS
from autobahn.wamp import auth
from twisted.internet import _sslverify

class Component(ApplicationSession):

    def onConnect(self):
        print("Client connected. Starting WAMP-Ticket authentication on "
              "realm {} as crsb_user {}".format(REALM, USER))
        # TODO change back "docker" to USER.encode("utf8"))
        self.join(REALM, [u"wampcra"], u"docker")

    def onChallenge(self, challenge):
        if challenge.method == "wampcra":
            print("WAMP-Ticket challenge received: {}".format(challenge))
            signature = auth.compute_wcs(SECRET.encode('utf8'),
                                         challenge.extra['challenge'].encode('utf8'))
            return signature.decode('ascii')
        else:
            raise Exception("Invalid authmethod {}".format(challenge.method))

    @inlineCallbacks
    def onJoin(self, details):
        try:
            now = yield self.call(u'comp.task.state_update', message)
        except Exception as e:
            print("Error: {}".format(e))
        else:
            print("Message response: {}".format(now))
        self.leave()

    def onDisconnect(self):
        print("disconnected")
        reactor.stop()

_sslverify.platformTrust = lambda: None
runner = ApplicationRunner(
    URL,
    REALM,
    ssl=optionsForClientTLS(X509_COMMON_NAME, trustRoot=None)
)

runner.run(Component)