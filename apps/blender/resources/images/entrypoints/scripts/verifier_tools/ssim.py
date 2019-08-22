import numpy
from .skimage import compare_ssim

import sys


## ======================= ##
##
class MetricSSIM:

    ## ======================= ##
    ##
    @staticmethod
    def compute_metrics(image1, image2):
        image1 = image1.convert("RGB")
        image2 = image2.convert("RGB")

        np_image1 = numpy.array(image1)
        np_image2 = numpy.array(image2)

        structualSim = compare_ssim(np_image1, np_image2, multichannel=True)

        result = dict()
        result["ssim"] = structualSim

        return result

    ## ======================= ##
    ##
    @staticmethod
    def get_labels():
        return ["ssim"]


## ======================= ##
##
def run():
    first_image = sys.argv[1]
    second_image = sys.argv[2]

    ssim = MetricSSIM()

    print(ssim.compute_metrics(first_image, second_image))


if __name__ == "__main__":
    run()
