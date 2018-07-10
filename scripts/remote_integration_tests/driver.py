
import urllib3
import json
import time
from datetime import timedelta,datetime
import re

def wait_until_timeout(cond, timeout=30, sleep_secs=5):
    te = datetime.now() + timedelta(seconds=timeout)
    while datetime.now() < te:
        if not cond():
            return
        time.sleep(sleep_secs)
    raise Timeout()



class Timeout(Exception):

    pass


class UnexpectedEof(Exception):
    pass

class Driver:

    def __init__(self, url = "http://10.30.10.201:4545"):
        self.http = urllib3.PoolManager()
        self.url = url

    def get(self, path):
        try:
            url = "%s/%s" % (self.url, path)
            f = self.http.request('GET', url)
            return json.loads(f.data)
        except:
            raise

    def path_url(self, path):
        return "%s/%s" % (self.url, path)

    def post(self, path, data):
        url = "%s/%s" % (self.url, path)
        r = self.http.request('POST', url, body= json.dumps(data), headers={'Content-Type': 'application/json'})
        f = r.data.decode('utf-8')

        return json.loads(f)

    def worker(self, id, node = None):
        return Worker(self, id, node)

    def build_env(self):
        return EnvBuilder(self)

    def env(self, id):
        return Env(self, id)

    def clear(self):
        w = self.get('worker')
        self.post('clean', True)
        time.sleep(2)
        for i in range(5):
            w2=self.get("worker")
            if len(w) == len(w2):
                break
            time.sleep(5)


class Worker:

    def __init__(self, driver, id, node):
        self.driver = driver
        self.id = id
        self._node = node
        self._ev = None

        self._golemapp = None

    def ip(self):
        return self._node['ip']

    def is_macos(self):
        return self._node['os'] == 'MacOs'

    def _req(self, cmd):
        path = "worker/%d/send" % (self.id, )

        cmd_id = self.driver.post(path, cmd)
        return self.wait_for(cmd_id)

    def url_process(self):
        return self.driver.path_url("worker/%d/process" % (self.id,))

    def spawn(self, executable, args):
        process_id = self.driver.post("worker/%d/process" % (self.id,), {'executable': executable, 'args': args})
        return Process(self.driver, self.id, process_id)

    def output(self, process_id):
        url = self.driver.path_url("worker/%d/process/%d/output" % (self.id, process_id))
        f = urllib3.urlopen(url)
        return json.loads(f.read())

    def wait_for(self, process_id):
        #url = self.driver.path_url("worker/%d/waitFor/%d" % (self.id, process_id))

        print("waitfor")
        try:
            return self.driver.get("worker/%d/waitFor/%d" % (self.id, process_id))
        except:
            print("waitfor done")

    def send_template(self, body, out_f):
        self._req({"TemplateFile": {"body": body, "out_file": out_f}})

    def get_reqs(self):
        return self.driver.get('worker/%d/req' %(self.id,))

    def golemapp(self):
        if self._golemapp is None:
            app = [ it[0] for it in self.get_reqs() if 'Spawn' in it[1] and it[1]['Spawn']['executable'].find('golemapp') >=0 ]
            self._golemapp = Process(self.driver, self.id, app[-1])
        return self._golemapp

    def cli(self, *args):
        work_dir = self._node['work_dir']
        xcli = self.spawn(work_dir + "/golemcli", args)
        self.wait_for(xcli.process_id)
        return xcli

    def json_cli(self, *args):
        args = args + ('--json',)
        c = self.cli(*args)
        o = json.loads(''.join([ l[1] for l in c.output_all() if l[0] == 'Out' ]))
        return o

    def cmd(self, cmd, *args):
        return self.spawn(cmd, args)

    def cmd_net_connect(self, ip, port='40102'):
        return self.cli("network", "connect", ip, port).output_all()

    def cmd_net_show(self):
        return self.json_cli('network', 'show')


class Process:
    def __init__(self, driver, worker_id, process_id):
        self.driver = driver
        self.worker_id = worker_id
        self.process_id = process_id
        self.out_position = 0

    def _req(self, cmd):
        path = "worker/%d/send" % (self.worker_id, )

        cmd_id = self.driver.post(path, cmd)
        return self.wait_for(cmd_id)


    def wait(self):
        return self.driver.get("worker/%d/waitFor/%d" % (self.worker_id, self.process_id))

    def output_since(self, since):
        t = 1
        for i in range(6):
            try:
                return self.driver.get("worker/%d/process/%d/output?since=%d" % (self.worker_id, self.process_id, since))
            except:
                time.sleep(t)
                t = t*2
                print("retry")


    def output(self):
        for i in range(15):
            try:
                return self.driver.get("worker/%d/process/%d/output" % (self.worker_id, self.process_id))
            except:
                time.sleep(5)
                print("retry")
        raise Timeout()

    def output_all(self, timeout=300):
        buf = []
        te = datetime.now() + timedelta(seconds=timeout)
        while datetime.now() < te:
            for line in self.output_since(len(buf) + self.out_position):
                print(line)
                buf.append(line)
                if line[0] == 'Eof':
                    return buf
            print("--")
            time.sleep(5)
        raise Timeout()

    def _wait_for_output(self, pred, timeout=60, fail_on_eof=True, mark_position=True):
        buf = []
        te = datetime.now() + timedelta(seconds=timeout)
        while datetime.now() < te:
            for line in self.output_since(len(buf) + self.out_position):
                print(line)
                buf.append(line)
                if line[0] == 'Eof' and fail_on_eof:
                    raise UnexpectedEof()

                if pred(line):
                    if mark_position:
                        self.out_position = self.out_position + len(buf)
                    return (line, buf)

            time.sleep(5)
        raise Timeout()

    def wait_for_output(self, outp, timeout = 60, fail_on_eof = True, mark_position = True):
        buf = []
        te = datetime.now() + timedelta(seconds=timeout)
        while datetime.now() < te:
            for line in self.output_since(len(buf) + self.out_position):
                print(line)
                buf.append(line)
                if line[0] == 'Eof' and fail_on_eof:
                    raise UnexpectedEof()

                if line[1].find(outp) >= 0:
                    if mark_position:
                        self.out_position = self.out_position + len(buf)
                    return True
            time.sleep(5)
        print("not found: ", outp)
        raise Timeout()


    def wait_for_output_multi(self, outp, timeout = 60, fail_on_eof = True, mark_position = True):

        rexpr = "|".join([ "(%s)" % (v,) for v in outp.values()])

        pattern = re.compile(rexpr)


        def pred(line):
            r= pattern.search(line[1])
            print(r)
            return r


        (line, buf) = self._wait_for_output(pred, timeout, fail_on_eof, mark_position)

        for k in outp.keys():
            if re.match(outp[k], line[1]):
                return k
        return None


    def kill(self):
        req_id = self._req({'StopProcess': {'pid': self.process_id}})
        return self.driver.get("worker/%d/waitFor/%d" % (self.worker_id, req_id))

class Env:

    def __init__(self, driver, id):
        self._driver = driver
        self._id = id
        self._ev = None
        self._nodes_status = {}

    def get(self):
        return self._driver.get('env/%s' % (self._id,))

    def wait(self, timeout = 300):
        wait_until_timeout(self.is_pending, timeout=timeout, sleep_secs=15)

    def is_valid(self):
        return len([it for it in self._nodes_status.values() if it == 'Fail']) == 0

    def is_pending(self):
        try:
            r = self.get()
            pending = False
            for node in r["nodes"]:
                status = node['status']
                id = node['id']
                old_status = None
                if id in self._nodes_status:
                    old_status = self._nodes_status[id]
                self._nodes_status[id] = status
                if old_status != status:
                    print('node', id, node['os'], status)

                if status != 'Working' and status != 'Fail':
                    pending=True
            return pending
        except:
            print("fail")
            return False

    def cache_get(self):
        if self._ev is None:
            self._ev = self.get()
        return self._ev

    def worker(self, role):
        ev = self.cache_get()
        for node in ev['nodes']:
            if node['role'] == role:
                return self._driver.worker(node['id'], node)

    def clear(self):
        self._driver.clear()


class EnvBuilder:

    def __init__(self, driver):
        self.driver = driver
        self.cmd = {'name': '', 'expire': 300, 'assets': [], 'nodes':[]}

    def name(self, name):
        self.cmd['name'] = name
        return self

    def expire(self, expire):
        self.cmd['expire'] = expire
        return self

    def asset(self, asset):
        self.cmd['assets'].append(asset)
        return self

    def nodes(self, branch, version, peers):
        for role in peers.keys():
            os = peers[role]
            self.add_node(branch, version, role, os)

        return self

    def add_node(self, branch, version, role, os):
        if os == 'Ubuntu':
            if version.find('dev') > 0:
                version = version[:-2]
            out_os = 'linux'
        elif os == 'MacOs':
            out_os = 'macOS'
        else:
            out_os = os.lower()

        download_url = "https://buildbot.golem.network/artifacts/%s/golem-%s-%s.tar.gz" % (branch, version, out_os,)
        work_dir = "run/golem-%s" % (version,)
        if os == 'Windows':
            download_url = "https://buildbot.golem.network/artifacts/%s/golem-%s-%s.zip" % (branch, version, out_os,)
            work_dir = "run/dist/golem-%s" % (version,)
        self.cmd['nodes'].append({'role': role, 'os': os, 'download': download_url, 'work_dir': work_dir})

    def build(self):
        env = self.driver.post('env/', self.cmd)
        return self.driver.env(env['id'])




__all__ = ['Driver']
