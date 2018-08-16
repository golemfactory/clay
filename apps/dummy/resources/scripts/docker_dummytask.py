from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run
from autobahn.wamp import auth
from twisted.internet import _sslverify

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

    # -------------------------------------------------------------------
    # Temporary testing for communications by sockets
    #####################################################################

    state_update_info = {u"task_id": params.task_id.decode("utf-8"),
                         u"subtask_id": params.subtask_id.decode("utf-8"),
                         u"state_update_id": u"1"}
    message = {
        u"info": state_update_info,
        u"data": {u"aa": u"bb"}
    }

    SECRET = "secret123"

    print(message)

    from twisted.internet import reactor
    from twisted.internet.defer import inlineCallbacks
    from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner
    from twisted.internet._sslverify import optionsForClientTLS

    class Component(ApplicationSession):
        """
        An application component using the time service.
        """

        def onConnect(self):
            print("Client connected. Starting WAMP-Ticket \
                        authentication on realm {} \
                        as crsb_user {}".format(
                "golem", "docker"))
            self.join(u"golem", [u"wampcra"], u"docker")

        def onChallenge(self, challenge):
            print("aaa")
            if challenge.method == "wampcra":
                print("WAMP-Ticket challenge received: {}".format(challenge))
                signature = auth.compute_wcs(SECRET.encode('utf8'),
                                             challenge.extra['challenge'].encode('utf8'))
                return signature.decode('ascii')
            else:
                raise Exception("Invalid authmethod {}".format(challenge.method))

        @inlineCallbacks
        def onJoin(self, details):
            print("session attached")
            try:
                now = yield self.call(u'comp.task.state_update', message)
                # now = yield self.call(u'comp.environments', message)

            except Exception as e:
                print("Error: {}".format(e))
            else:
                print("Message response: {}".format(now))

            self.leave()

        def onDisconnect(self):
            print("disconnected")
            reactor.stop()


    if __name__ == '__main__':
        import six

        _sslverify.platformTrust = lambda: None

        url = u"wss://172.17.0.1:61000"
        if six.PY2 and type(url) == six.binary_type:
            url = url.decode('utf8')
        realm = u"golem"
        runner = ApplicationRunner(url, realm, ssl=optionsForClientTLS(u"golem.local", trustRoot=None))
        runner.run(Component)


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
