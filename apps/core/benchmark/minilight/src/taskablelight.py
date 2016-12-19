import time

from taskablerenderer import TaskableRenderer
from renderworker import RenderWorker
from img import Img
from rendertaskcreator import ThreadRenderWorkerPool

import task_data_0

INPUT_W  = 50
INPUT_H  = 50
SAMPLES  = 30
TIMESLC  = 1.0
TIMEOUT  = 3600.0
IMG_NAME = "test_sliced_img.ppm"
MAX_CONCURRENT_WORKERS = 25


def save_image(img_name, w, h, data, num_samples):
    if not data:
        print "No data to write"
        return False

    img = Img(w, h)
    img.copyPixels(data)

    image_file = open(img_name, 'wb')
    img.get_formatted(image_file, num_samples)
    image_file.close()


if __name__ == "__main__":

    pool = ThreadRenderWorkerPool()
    tr = TaskableRenderer(INPUT_W, INPUT_H, SAMPLES, task_data_0.deserialized_task, TIMESLC, TIMEOUT)
    tr.start()
    lastPrint = time.time()

    while not tr.isFinished():
        if pool.activeCount() < MAX_CONCURRENT_WORKERS and tr.hasMoreTasks():
            pool.createNextWorker(tr)

        time.sleep(0.2) #arbitrary sleep time

        if time.time() - lastPrint > 2.0:
            lastPrint = time.time()
            print "Active worker count {}".format(pool.activeCount())
            tr.printStats()

    pool.joinAll()

    tr.printStats()

    print "All tasks finished gracefully"
    print "Writing result image {}".format(IMG_NAME)
    save_image(IMG_NAME, INPUT_W, INPUT_H, tr.getResult(), SAMPLES)
