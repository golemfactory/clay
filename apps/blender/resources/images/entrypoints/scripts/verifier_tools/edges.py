from PIL import Image, ImageFilter
import numpy
from .skimage import compare_mse


import sys


## ======================= ##
##
class MetricEdgeFactor:


    ## ======================= ##
    ##
    @staticmethod
    def compute_metrics( image1, image2 ):

        image1 = image1.convert("RGB")
        image2 = image2.convert("RGB")

        edged_image1 = image1.filter( ImageFilter.FIND_EDGES )
        edged_image2 = image2.filter( ImageFilter.FIND_EDGES )

        np_image1 = numpy.array( edged_image1 )
        np_image2 = numpy.array( edged_image2 )

        ref_edge_factor = numpy.mean( np_image1 )
        comp_edge_factor = numpy.mean( np_image2 )

        edge_factor = compare_mse( np_image1, np_image2 )

        result = dict()
        result[ "ref_edge_factor" ] = ref_edge_factor
        result[ "comp_edge_factor" ] = comp_edge_factor
        result[ "edge_difference" ] = edge_factor

        return result

    ## ======================= ##
    ##
    @staticmethod
    def get_labels():
        return [ "ref_edge_factor", "comp_edge_factor", "edge_difference" ]

## ======================= ##
##
def run():

    first_img = sys.argv[ 1 ]
    second_img = sys.argv[ 2 ]

    first_img = Image.open( first_img )
    second_img = Image.open( second_img )

    ssim = MetricEdgeFactor()

    print( ssim.compute_metrics( first_img, second_img ) )



if __name__ == "__main__":
    run()
