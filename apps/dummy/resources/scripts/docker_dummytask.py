from __future__ import print_function

import imp
import os

import params  # This module is generated before this script is run


def run(data_files, subtask_data, difficulty, result_size, result_file):

    print("DIRS ", str(os.listdir("/")))
    print("DIRS ", str(os.listdir(params.RESOURCES_DIR)))
    print("DIRS ", str(os.listdir("{}/code".format(params.RESOURCES_DIR))))
    print("DIRS ", str(os.listdir(params.OUTPUT_DIR)))

    code_file = os.path.join(params.RESOURCES_DIR, "code", "computing.py")
    computing = imp.load_source("code", code_file)

    data_file = os.path.join(params.RESOURCES_DIR, "data", data_files[0])
    result_path = os.path.join(params.OUTPUT_DIR, result_file)

    solution = computing.run_dummy_task(data_file,
                                        subtask_data,
                                        difficulty,
                                        result_size)

    # TODO try catch and log errors. Issue #2425
    with open(result_path, "w") as f:
        f.write("{}".format(solution))

    # -------------------------------------------------------------------
    # Temporary testing for communications by files
    #####################################################################
    # import json
    # import time
    #
    #
    # with open(os.path.join(params.MESSAGES_IN_DIR, "first.json"), "w+") as f:
    #     json.dump({"got_messages": "aaa"}, f)
    # with open(os.path.join(params.MESSAGES_OUT_DIR, "second.json"), "w+") as f:
    #     json.dump({"got_messages": "vvv"}, f)
    #
    # time.sleep(3)
    #
    # if difficulty == 0xffff0000:
    #     for _ in range(10):
    #         time.sleep(1)
    #         for fname in os.listdir(params.MESSAGES_IN_DIR):
    #             if not fname.startswith("."):
    #                 with open(os.path.join(params.MESSAGES_IN_DIR, fname), "r") as f:
    #                     print(os.path.join(params.MESSAGES_IN_DIR, fname))
    #                     x = f.read()
    #                     print(x)
    #                     x = json.loads(x)
    #                 with open(os.path.join(params.MESSAGES_OUT_DIR, fname + "out"), "w+") as f:
    #                     json.dump({"got_messages": x["got_messages"] + "bbb"}, f)

    # -------------------------------------------------------------------
    # Temporary testing for communications by sockets
    #####################################################################

    from twisted.internet import reactor
    from twisted.internet.defer import inlineCallbacks

    from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner

    class Component(ApplicationSession):
        """
        An application component using the time service.
        """

        @inlineCallbacks
        def onJoin(self, details):
            print("session attached")
            try:
                now = yield self.call(u'net.p2p.port')
            except Exception as e:
                print("Error: {}".format(e))
            else:
                print("Current time from time service: {}".format(now))

            self.leave()

        def onDisconnect(self):
            print("disconnected")
            reactor.stop()

    if __name__ == '__main__':
        import six
        url = u"ws://172.17.0.1:61000"
        if six.PY2 and type(url) == six.binary_type:
            url = url.decode('utf8')
        realm = u"golem"
        runner = ApplicationRunner(url, realm)
        runner.run(Component)


run(params.data_files,
    params.subtask_data,
    params.difficulty,
    params.result_size,
    params.result_file)
