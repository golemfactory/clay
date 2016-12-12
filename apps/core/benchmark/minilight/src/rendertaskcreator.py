from randommini import Random
from renderworker import RenderWorker
from threading import Thread, active_count

class ThreadedRenderWorker(Thread):
    def __init__(self, rw):
        super(ThreadedRenderWorker, self).__init__()
        self.worker = rw
        self.result = None

    def getWorker(self):
        return self.worker

    def getResult(self):
        return self.result

    def run(self):
        self.result = self.worker.render()

class ThreadRenderWorkerPool:

    def __init__(self, baseExpectedSpeed = 1600.0):
        self.rnd = Random()
        self.baseSpeed = baseExpectedSpeed
        self.workers = []

    def createNextWorker(self, taskable_renderer):
        speed = (0.5 + self.rnd.real64()) * self.baseSpeed
        task = taskable_renderer.getNextTask(speed)

        if task:
            worker = ThreadedRenderWorker(RenderWorker(task))
            self.workers.append(worker)

            worker.start()
            
            return worker

        return None

    def activeCount(self):
        return active_count() - 1

    def joinAll(self):
        for w in self.workers:
            w.join()
