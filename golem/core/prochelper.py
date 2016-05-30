import os
import psutil
import fnmatch
import time
import logging

from simpleserializer import SimpleSerializer
from simpleenv import SimpleEnv
from variables import DEFAULT_PROC_FILE, MAX_PROC_FILE_SIZE

logger = logging.getLogger(__name__)


class ProcessService(object):
    """ Keeps information about active application instances and gives them adequate numbers that may be used
    to combine them with proper configuration options."""

    def __init__(self, ctl_file_name=DEFAULT_PROC_FILE):
        """ Create new process service instance
        :param str ctl_file_name: process working file were information about active applications is written
        """
        ctl_file = SimpleEnv.env_file_name(ctl_file_name)

        self.maxFileSize = MAX_PROC_FILE_SIZE
        self.fd = -1
        self.ctl_file = ctl_file
        self.state = {}

        if not os.path.exists(ctl_file) or os.path.getsize(ctl_file) < 2:
            if self.__acquire_lock():
                self.__write_state_snapshot()

    def lock_state(self):
        """ Acquire access to the process control file and read process state
        :return bool: True if access was acquired, False otherwise
        """
        if self.__acquire_lock():
            self.__read_state_snapshot()
            return True

        return False

    def unlock_state(self):
        """ Write process state in the process control file
        :return:
        """
        if self.fd > 0:
            self.__write_state_snapshot()

    def register_self(self, extra_data=None):
        """ Register new application instance in process control file. Remove inactive process and get earliest
        available number
        :param extra_data: additional information that should be saved
        :return int: process number
        """
        spid = int(os.getpid())
        timestamp = time.time()

        if self.lock_state():
            id_ = self.__update_state()
            self.state[spid] = [timestamp, id_, extra_data]
            self.unlock_state()
            logger.info("Registering new process - PID {} at time {} at location {}".format(spid, timestamp, id_))

            return id_

        return -1

    @staticmethod
    def list_all(filter_=None):
        """ Return list of all active program instances on this machine
        :param str filter_: pattern for the unix shell-style wildcard
        :return:
        """
        ret_list = []

        if not filter_:
            filter_ = "*"

        for p in psutil.process_iter():
            if fnmatch.fnmatch(p.__str__(), filter_):
                ret_list.append(p)

        return ret_list

    def __acquire_lock(self, flags=os.O_EXCL):
        flags |= os.O_EXCL | os.O_RDWR

        try:
            if not os.path.exists(self.ctl_file):
                flags |= os.O_CREAT

            self.fd = os.open(self.ctl_file, flags)

            return True
        except Exception as ex:
            logger.error("Failed to acquire lock due to {}".format(ex))
            return False

    def __release_lock(self):
        if self.fd > 0:
            os.close(self.fd)
            self.fd = -1

    def __read_state_snapshot(self):
        os.lseek(self.fd, 0, 0)
        data = os.read(self.fd, self.maxFileSize)
        self.state = SimpleSerializer.loads(data)

    def __write_state_snapshot(self):
        data = SimpleSerializer.dumps(self.state)

        os.lseek(self.fd, 0, 0)

        # FIXME: one hell of a hack but its pretty hard to truncate a file on Windows using low level API
        hack = os.fdopen(self.fd, "w")
        hack.truncate(len(data))
        os.write(self.fd, data)

        hack.close()

    def __update_state(self):
        pids = psutil.pids()
        updated_state = {}
        ids = []

        for p in self.state:
            if int(p) in pids:
                updated_state[p] = self.state[p]
                ids.append(self.state[p][1])  # local_id
            else:
                logger.info("Process PID {} is inactive - removing".format(p))

        self.state = updated_state

        if len(ids) > 0:
            sids = sorted(ids, key=int)
            for i in range(len(sids)):
                if i < sids[i]:
                    return i

        return len(ids)


if __name__ == "__main__":
    ps = ProcessService("test_ctl.ctl")
    # print os.getpid()

    # for p in ps.list_all(filter_ = "*python.exe*"):
    #     print p

    import random

    id__ = ps.register_self()
    print "Registered id {}".format(id__)
    time.sleep(5.0 + 10.0 * random.random())
