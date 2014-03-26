from threading import Lock, Thread
from time import time

class TaskableRenderer(Thread):

    def __init__( self, w, h, num_samples, scene_data, timeoutTime ):
        super( TaskableRenderer, self ).__init__()

        self.w = w
        selg.h = h
        self.num_samples = num_sampes
        self.scene_data = scene_data

        self.timeoutTime = timeoutTime
        self.startTime = time()

        #FIXME: this should be a bit more sophisticated structure (to collect more than one result per pixel and to calc some stats using this data)
        self.data = [0.0] * w * h * 3

        self.lock = Lock()

    def start( self ):

    def run(self):
        return super(TaskableRenderer, self).run()
    def start
    def 