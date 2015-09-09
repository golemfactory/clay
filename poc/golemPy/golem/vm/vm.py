from threading import Lock
import logging
import abc

from MemoryChecker import MemoryChecker

logger = logging.getLogger(__name__)

class IGolemVM:
    #######################
    def __init__(self):
        pass

    #######################
    def get_progress(self):
        assert False

    #######################
    def interpret(self, codeResource):
        pass


class TaskProgress:
    #######################
    def __init__(self):
        self.lock = Lock()
        self.progress = 0.0

    #######################
    def get(self):
        with self.lock:
            return self.progress

    #######################
    def set(self, val):
        with self.lock:
            self.progress = val


class GolemVM(IGolemVM):
    #######################
    def __init__(self):
        IGolemVM.__init__(self)
        self.src_code = ""
        self.scope = {}
        self.progress = TaskProgress()

    #######################
    def get_progress(self):
        return self.progress.get()
      
    #######################  
    def runTask(self, src_code, extra_data):
        self.src_code = src_code
        self.scope = extra_data
        self.scope[ "taskProgress" ] = self.progress

        return self._interpret()

    def end_comp(self):
        pass

    #######################
    @abc.abstractmethod
    def _interpret(self):
        return

##############################################
import multiprocessing as mp

class PythonVM(GolemVM):

    def _interpret(self):
        exec self.src_code in self.scope
        return self.scope[ "output" ]

##############################################
import multiprocessing as mp

class PythonProcVM(GolemVM):
    def __init__(self):
        GolemVM.__init__(self)
        self.proc = None

    def end_comp(self):
        if self.proc:
            self.proc.terminate()

    def _interpret(self):
        del self.scope['taskProgress']
        manager = mp.Manager()
        scope = manager.dict(self.scope)
        self.proc = mp.Process(target = execCode, args=(self.src_code, scope))
        self.proc.start()
        self.proc.join()
        return scope.get("output")

def execCode(src_code, scopeManager):
    scope = dict(scopeManager)
    exec src_code in scope
    scopeManager["output"] = scope["output"]

##############################################
class PythonTestVM(GolemVM):
    def _interpret(self):
        mc = MemoryChecker()
        mc.start()
        try:
            exec self.src_code in self.scope
        except Exception, e:
            logger.error("Execution failure {}".format(str(e)))
        finally:
            estimated_mem = mc.stop()
        logger.info("Estimated memory for taks: {}".format(estimated_mem))
        return self.scope[ "output" ], estimated_mem

