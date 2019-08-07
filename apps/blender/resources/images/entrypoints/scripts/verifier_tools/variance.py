import numpy


## ======================= ##
##
class ImageVariance:
    

    ## ======================= ##
    ##
    @staticmethod
    def compute_metrics( image1, image2 ):

        image1 = image1.convert("RGB")
        image2 = image2.convert("RGB")
        
        np_image1 = numpy.array( image1 )
        np_image2 = numpy.array( image2 )
        
        reference_variance = numpy.var( np_image1, axis=( 0, 1 ) )
        image_variance = numpy.var( np_image2, axis=( 0, 1 ) )
        
        reference_variance = reference_variance[ 0 ] + reference_variance[ 1 ] + reference_variance[ 2 ]
        image_variance = image_variance[ 0 ] + image_variance[ 1 ] + image_variance[ 2 ]
        
        result = dict()
        result[ "reference_variance" ] = reference_variance
        result[ "image_variance" ] = image_variance
        result[ "variance_difference" ] = image_variance - reference_variance
        
        return result
    
    ## ======================= ##
    ##
    @staticmethod
    def get_labels():
        return [ "reference_variance", "image_variance", "variance_difference"]
        
        