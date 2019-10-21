import numpy
import math
from .skimage import compare_psnr

import sys


## ======================= ##
##
class MetricPSNR:

    ## ======================= ##
    ##
    @staticmethod
    def compute_metrics(image1, image2):
        image1 = image1.convert("RGB")
        image2 = image2.convert("RGB")

        np_image1 = numpy.array(image1)
        np_image2 = numpy.array(image2)

        psnr = compare_psnr(np_image1, np_image2)

        if math.isinf(psnr):
            psnr = numpy.finfo(numpy.float32).max

        result = dict()
        result["psnr"] = psnr

        return result

    ## ======================= ##
    ##
    @staticmethod
    def get_labels():
        return ["psnr"]


## ======================= ##
##
def run():
    first_image = sys.argv[1]
    second_image = sys.argv[2]

    psnr = MetricPSNR()

    print(psnr.compute_metrics(first_image, second_image))


if __name__ == "__main__":
    run()
