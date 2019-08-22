import pywt
import numpy
from PIL import Image

import sys


def calculate_sum(coefficient):
    return sum(sum(coefficient ** 2))


def calculate_size(coefficient):
    shape = coefficient.shape
    return shape[0] * shape[1]


def calculate_mse(coefficient1, coefficient2, low, high):
    if low == high:
        if low == 0:
            high = low + 1
        else:
            low = high - 1
    sum_ = 0
    count = 0
    for i in range(low, high):
        if type(coefficient1[i]) is tuple:
            sum_ += calculate_sum(coefficient1[i][0] - coefficient2[i][0])
            sum_ += calculate_sum(coefficient1[i][1] - coefficient2[i][1])
            sum_ += calculate_sum(coefficient1[i][2] - coefficient2[i][2])
            count += 3 * coefficient1[i][0].size
        else:
            sum_ += calculate_sum(coefficient1[i] - coefficient2[i])
            count += coefficient1[i].size
    if (count == 0):
        return 0
    else:
        return sum_ / count


## ======================= ##
##
def calculate_frequencies(coefficient1, coefficient2):
    num_of_levels = len(coefficient1)
    start_level = num_of_levels - 3

    frequencies = list()

    for i in range(start_level, num_of_levels):
        abs_coeff1 = numpy.absolute(coefficient1[i])
        abs_coeff2 = numpy.absolute(coefficient2[i])

        sum_coeffs1 = sum(sum(sum(abs_coeff1)))
        sum_coeffs2 = sum(sum(sum(abs_coeff2)))

        diff = numpy.absolute(sum_coeffs2 - sum_coeffs1) / (
                    3 * coefficient1[i][0].size)

        frequencies = [diff] + frequencies

    return frequencies


## ======================= ##
##
class MetricWavelet:

    ## ======================= ##
    ##
    @staticmethod
    def compute_metrics(image1, image2):

        image1 = image1.convert("RGB")
        image2 = image2.convert("RGB")

        np_image1 = numpy.array(image1)
        np_image2 = numpy.array(image2)

        result = dict()
        result["wavelet_db4_base"] = 0
        result["wavelet_db4_low"] = 0
        result["wavelet_db4_mid"] = 0
        result["wavelet_db4_high"] = 0

        for i in range(0, 3):
            coefficient1 = pywt.wavedec2(np_image1[..., i], "db4")
            coefficient2 = pywt.wavedec2(np_image2[..., i], "db4")

            total_length = len(coefficient1) - 1
            one_third_of_length = int(total_length / 3)
            two_thirds_of_length = int(total_length * 2 / 3)

            result["wavelet_db4_base"] += calculate_mse(
                coefficient1,
                coefficient2,
                0,
                1
            )
            result["wavelet_db4_low"] = result[
                "wavelet_db4_low"
            ] + calculate_mse(
                coefficient1, coefficient2, 1, 1 + one_third_of_length
            )
            result["wavelet_db4_mid"] = result[
                "wavelet_db4_mid"
            ] + calculate_mse(
                coefficient1, coefficient2, 1 + one_third_of_length,
                1 + two_thirds_of_length
            )
            result["wavelet_db4_high"] = result[
                "wavelet_db4_high"
            ] + calculate_mse(
                coefficient1, coefficient2, 1 + two_thirds_of_length,
                1 + total_length
            )

        #
        result["wavelet_sym2_base"] = 0
        result["wavelet_sym2_low"] = 0
        result["wavelet_sym2_mid"] = 0
        result["wavelet_sym2_high"] = 0

        for i in range(0, 3):
            coefficient1 = pywt.wavedec2(np_image1[..., i], "sym2")
            coefficient2 = pywt.wavedec2(np_image2[..., i], "sym2")

            total_length = len(coefficient1) - 1
            one_third_of_length = int(total_length / 3)
            two_thirds_of_length = int(total_length * 2 / 3)

            result["wavelet_sym2_base"] += calculate_mse(
                coefficient1,
                coefficient2,
                0,
                1
            )
            result["wavelet_sym2_low"] = result[
                "wavelet_sym2_low"
             ] + calculate_mse(
                coefficient1, coefficient2, 1, 1 + one_third_of_length
            )
            result["wavelet_sym2_mid"] = result[
                "wavelet_sym2_mid"
             ] + calculate_mse(
                coefficient1, coefficient2, 1 + one_third_of_length,
                1 + two_thirds_of_length
            )
            result["wavelet_sym2_high"] = result[
                "wavelet_sym2_high"
            ] + calculate_mse(
                coefficient1, coefficient2, 1 + two_thirds_of_length,
                1 + total_length
            )

        # Frequency metrics based on haar wavlets
        result["wavelet_haar_freq_x1"] = 0
        result["wavelet_haar_freq_x2"] = 0
        result["wavelet_haar_freq_x3"] = 0

        result["wavelet_haar_base"] = 0
        result["wavelet_haar_low"] = 0
        result["wavelet_haar_mid"] = 0
        result["wavelet_haar_high"] = 0

        for i in range(0, 3):
            coefficient1 = pywt.wavedec2(np_image1[..., i], "haar")
            coefficient2 = pywt.wavedec2(np_image2[..., i], "haar")

            frequencies = calculate_frequencies(coefficient1, coefficient2)

            result["wavelet_haar_freq_x1"] = result["wavelet_haar_freq_x1"] + \
                                             frequencies[0]
            result["wavelet_haar_freq_x2"] = result["wavelet_haar_freq_x2"] + \
                                             frequencies[1]
            result["wavelet_haar_freq_x3"] = result["wavelet_haar_freq_x3"] + \
                                             frequencies[2]

            total_length = len(coefficient1) - 1
            one_third_of_length = int(total_length / 3)
            two_thirds_of_length = int(total_length * 2 / 3)

            result["wavelet_haar_base"] += calculate_mse(
                coefficient1,
                coefficient2,
                0,
                1
            )
            result["wavelet_haar_low"] += calculate_mse(
                coefficient1,
                coefficient2,
                1,
                1 + one_third_of_length
            )
            result["wavelet_haar_mid"] += calculate_mse(
                coefficient1,
                coefficient2,
                1 + one_third_of_length,
                1 + two_thirds_of_length
            )
            result["wavelet_haar_high"] += calculate_mse(
                coefficient1,
                coefficient2,
                1 + two_thirds_of_length,
                1 + total_length
            )

        return result

    ## ======================= ##
    ##
    @staticmethod
    def get_labels():
        return ["wavelet_sym2_base", "wavelet_sym2_low", "wavelet_sym2_mid",
                "wavelet_sym2_high", "wavelet_db4_base", "wavelet_db4_low",
                "wavelet_db4_mid", "wavelet_db4_high", "wavelet_haar_base",
                "wavelet_haar_low", "wavelet_haar_mid", "wavelet_haar_high",
                "wavelet_haar_freq_x1", "wavelet_haar_freq_x2",
                "wavelet_haar_freq_x3"]


## ======================= ##
##
def run():
    first_image = Image.open(sys.argv[1])
    second_image = Image.open(sys.argv[2])

    ssim = MetricWavelet()

    print(ssim.compute_metrics(first_image, second_image))


if __name__ == "__main__":
    run()
