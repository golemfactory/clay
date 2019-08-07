import pywt
import numpy
from PIL import Image

import sys

def calculate_sum( coeff ):
    return sum( sum( coeff ** 2 ) )

def calculate_size( coeff ):
    shape = coeff.shape
    return shape[ 0 ] * shape[ 1 ]

def calculate_mse( coeff1, coeff2, low, high ):
    if low == high:
        if low == 0:
            high = low + 1
        else:
            low = high - 1
    suma = 0
    num = 0
    for i in range( low, high ):
        if type( coeff1[ i ] ) is tuple:
            suma += calculate_sum( coeff1[ i ][ 0 ] - coeff2[ i ][ 0 ] )
            suma += calculate_sum( coeff1[ i ][ 1 ] - coeff2[ i ][ 1 ] )
            suma += calculate_sum( coeff1[ i ][ 2 ] - coeff2[ i ][ 2 ] )
            num += 3 * coeff1[ i ][ 0 ].size
        else:
            suma += calculate_sum(coeff1[i] - coeff2[i] )
            num += coeff1[ i ].size
    if( num == 0 ):
        return 0
    else:
        return suma / num

## ======================= ##
##
def calculate_frequencies( coeff1, coeff2 ):

    num_levels = len( coeff1 )
    start_level = num_levels - 3
    
    freq_list = list()
    
    for i in range( start_level, num_levels ):
        
        abs_coeff1 = numpy.absolute( coeff1[ i ] )
        abs_coeff2 = numpy.absolute( coeff2[ i ] )
        
        sum_coeffs1 = sum( sum( sum( abs_coeff1 ) ) )
        sum_coeffs2 = sum( sum( sum( abs_coeff2 ) ) )
        
        diff = numpy.absolute( sum_coeffs2 - sum_coeffs1 ) / ( 3 * coeff1[ i ][ 0 ].size )
        
        freq_list = [ diff ] + freq_list
    

    return freq_list
        
        
## ======================= ##
##
class MetricWavelet:

    ## ======================= ##
    ##
    @staticmethod
    def compute_metrics( image1, image2):

        image1 = image1.convert("RGB")
        image2 = image2.convert("RGB")

        np_image1 = numpy.array(image1)
        np_image2 = numpy.array(image2)

        result = dict()
        result["wavelet_db4_base"] = 0
        result["wavelet_db4_low"] = 0
        result["wavelet_db4_mid"] = 0
        result["wavelet_db4_high"] = 0

        for i in range(0,3):
            coeff1 = pywt.wavedec2( np_image1[...,i], "db4" )
            coeff2 = pywt.wavedec2( np_image2[...,i], "db4" )

            len_total = len( coeff1 ) - 1
            len_div_3 = int( len_total / 3 )
            len_two_thirds = int( len_total * 2 / 3 )

            result[ "wavelet_db4_base" ] += calculate_mse( coeff1, coeff2, 0, 1 )
            result[ "wavelet_db4_low" ] = result[ "wavelet_db4_low" ] + calculate_mse( coeff1, coeff2, 1, 1 + len_div_3 )
            result[ "wavelet_db4_mid" ] = result[ "wavelet_db4_mid" ] + calculate_mse( coeff1, coeff2, 1 + len_div_3, 1 + len_two_thirds )
            result[ "wavelet_db4_high" ] = result[ "wavelet_db4_high" ] + calculate_mse( coeff1, coeff2, 1 + len_two_thirds, 1 + len_total )

        #
        result["wavelet_sym2_base"] = 0
        result["wavelet_sym2_low"] = 0
        result["wavelet_sym2_mid"] = 0
        result["wavelet_sym2_high"] = 0

        for i in range(0,3):
            coeff1 = pywt.wavedec2( np_image1[...,i], "sym2" )
            coeff2 = pywt.wavedec2( np_image2[...,i], "sym2" )

            len_total = len( coeff1 ) - 1
            len_div_3 = int( len_total / 3 )
            len_two_thirds = int( len_total * 2 / 3 )

            result[ "wavelet_sym2_base" ] += calculate_mse( coeff1, coeff2, 0, 1 )
            result[ "wavelet_sym2_low" ] = result[ "wavelet_sym2_low" ] + calculate_mse( coeff1, coeff2, 1, 1 + len_div_3 )
            result[ "wavelet_sym2_mid" ] = result[ "wavelet_sym2_mid" ] + calculate_mse( coeff1, coeff2, 1 + len_div_3, 1 + len_two_thirds )
            result[ "wavelet_sym2_high" ] = result[ "wavelet_sym2_high" ] + calculate_mse( coeff1, coeff2, 1 + len_two_thirds, 1 + len_total )
            
            
        # Frequency metrics based on haar wavlets
        result[ "wavelet_haar_freq_x1" ] = 0
        result[ "wavelet_haar_freq_x2" ] = 0
        result[ "wavelet_haar_freq_x3" ] = 0

        result["wavelet_haar_base"] = 0
        result["wavelet_haar_low"] = 0
        result["wavelet_haar_mid"] = 0
        result["wavelet_haar_high"] = 0

        for i in range(0,3):
            coeff1 = pywt.wavedec2( np_image1[...,i], "haar" )
            coeff2 = pywt.wavedec2( np_image2[...,i], "haar" )  
            
            freqs = calculate_frequencies( coeff1, coeff2 )
            
            result[ "wavelet_haar_freq_x1" ] = result[ "wavelet_haar_freq_x1" ] + freqs[ 0 ]
            result[ "wavelet_haar_freq_x2" ] = result[ "wavelet_haar_freq_x2" ] + freqs[ 1 ]
            result[ "wavelet_haar_freq_x3" ] = result[ "wavelet_haar_freq_x3" ] + freqs[ 2 ]

            len_total = len( coeff1 ) - 1
            len_div_3 = int( len_total / 3 )
            len_two_thirds = int( len_total * 2 / 3 )

            result[ "wavelet_haar_base" ] += calculate_mse( coeff1, coeff2, 0, 1 )
            result[ "wavelet_haar_low" ] += calculate_mse( coeff1, coeff2, 1, 1 + len_div_3 )
            result[ "wavelet_haar_mid" ] += calculate_mse( coeff1, coeff2, 1 + len_div_3, 1 + len_two_thirds )
            result[ "wavelet_haar_high" ] += calculate_mse( coeff1, coeff2, 1 + len_two_thirds, 1 + len_total )

        return result

    ## ======================= ##
    ##
    @staticmethod
    def get_labels():
        return [ "wavelet_sym2_base", "wavelet_sym2_low", "wavelet_sym2_mid", "wavelet_sym2_high", "wavelet_db4_base", "wavelet_db4_low", "wavelet_db4_mid", "wavelet_db4_high", "wavelet_haar_base", "wavelet_haar_low", "wavelet_haar_mid", "wavelet_haar_high", "wavelet_haar_freq_x1", "wavelet_haar_freq_x2", "wavelet_haar_freq_x3" ]


## ======================= ##
##
def run():
    first_img = Image.open( sys.argv[1] )
    second_img = Image.open( sys.argv[2] )

    ssim = MetricWavelet()

    print(ssim.compute_metrics(first_img, second_img))


if __name__ == "__main__":
    run()
