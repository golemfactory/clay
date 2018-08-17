import pytest
import driver
import time

class Session:

    def __init__(self):
        self.drv = driver.Driver()
        self.env = None
        self.sid = None
        self.requestor = None
        self._env_args = None

        self.drv.clear()

    def destroy(self):
        self.drv.clear()

    def build_env(self, os1, os2):
        self._env_args = (os1, os2)
        self.env = self.drv.build_env() \
            .name("test %s to %s" % (os1, os2,)).asset("test_task_1.zip").nodes(pytest.config.getoption('branch'), pytest.config.getoption('golemversion'),
                                                             {'Sid': os2, 'Requestor': os1}) \
            .build()

    def wait(self):
        for retry in range(3):
            try:
                self.env.wait()
                self.sid = self.env.worker('Sid')
                self.requestor = self.env.worker('Requestor')
            except driver.Timeout:
                if self.env.is_valid():
                    print("timeout retry")
                    self.drv.clear()
                    self.build_env(*self._env_args)
                    time.sleep(15)
                else:
                    raise driver.Timeout()

    def sid_ready(self):
        sid = self.sid
        sid_app = self.sid.golemapp()
        if self.sid.is_macos():
            print('macos')
            sid_app.wait_for_output('DockerMachine: starting golem', timeout=900)
            p = sid.cmd('docker-machine', 'restart', 'golem')
            time.sleep(2)
            p.output_all()


        sid_app.wait_for_output('Golem is listening on ports', timeout=900)



    def requestor_ready(self):
        requestor_app = self.requestor.golemapp()
        requestor_app.wait_for_output('Golem is listening on ports', timeout=600)

        sid_net = self.sid.cmd_net_show()
        if len(sid_net['values']) == 0:
            self.requestor.cmd_net_connect(self.sid.ip())
            time.sleep(2)
            self.sid.cli("network", "show").output_all()
        else:
            print('sid:', sid_net['values'])

        r_net = self.requestor.cmd_net_show()
        if len(r_net['values']) == 0:
            self.sid.cmd_net_connect(self.requestor.ip())
            time.sleep(2)
            self.requestor.cli("network", "show").output_all()


        self.requestor.cli("network", "show").output_all()

    def send_task(self):
        body = """{
"type": "Blender",
"name": "smok",
"timeout": "0:10:00",
"subtask_timeout": "0:09:50",
"subtasks": 1,
"bid": 1.0,
"resources": [
        "%RUNDIR%%SEP%test_task_1%SEP%puchacz_canopy.jpg",
        "%RUNDIR%%SEP%test_task_1%SEP%wlochaty3.blend"
],
"options": {
            "output_path": "%WORKDIR%",
            "format": "PNG",
                "frame_count": 1,
                "frames": "1",
                "compositing": false,
            "resolution": [
                320,
                240
            ]
        }
 }"""
        self.requestor.send_template(body, "test_1_subtask.json")
        cli = self.requestor.cli("tasks", "create", "run/test_1_subtask.json")

        outp = cli.output_all()

    def resend_task(self):
        cli = self.requestor.cli("tasks", "create", "run/test_1_subtask.json")
        outp = cli.output_all()

    def wait_for_task_send(self):
        requestor_app = self.requestor.golemapp()

        while True:
            r = requestor_app.wait_for_output_multi({'ok': 'Task.*added', 'nofunds': 'golem\\.transactions\\.ethereum\\.exceptions\\.NotEnoughFunds'}, timeout=300)
            if r == 'nofunds':
                print('waiting for funds')
                try:
                    requestor_app.wait_for_output('Conversion has been finalized', timeout=60)
                    time.sleep(20)
                except:
                    pass
                self.resend_task()
            else:
                break


    def wait_for_task_get(self):
        sid_app = self.sid.golemapp()
        sid_app.wait_for_output('Starting computation of subtask', timeout=300)


    def wait_for_verification(self):
        requestor_app = self.requestor.golemapp()
        requestor_app.wait_for_output('Finished verification', timeout=300)

class Base(object):

    @pytest.fixture(scope="session")
    def session(self, request):
        s = Session()
        request.addfinalizer(s.destroy)
        return s

    def test_init(self, session):
        self.env(session)

    def test_wait(self, session):
        session.wait()

    def test_sid_ready(self, session):
        session.sid_ready()

    def test_requestor_ready(self, session):
        session.requestor_ready()


    def test_create_task(self, session):
        session.send_task()

    def test_wait_for_task_send(self, session):
        session.wait_for_task_send()

    def test_wait_for_task_get(self, session):
        session.wait_for_task_get()

    def test_wait_for_verification(self, session):
        session.wait_for_verification()



@pytest.mark.incremental
class TestWindows2Ubuntu(Base):

    def env(self, session):
        return session.build_env('Windows', 'Ubuntu')

@pytest.mark.incremental
class TestMac2Ubuntu(Base):

    def env(self, session):
        return session.build_env('MacOs', 'Ubuntu')

@pytest.mark.incremental
class TestMac2Win(Base):

    def env(self, session):
        return session.build_env('MacOs', 'Windows')

@pytest.mark.incremental
class TestUbuntu2Windows(Base):

    def env(self, session):
        return session.build_env('Ubuntu', 'Windows')

@pytest.mark.incremental
class TestUbuntu2Ubuntu(Base):

    def env(self, session):
        return session.build_env('Ubuntu', 'Ubuntu')

