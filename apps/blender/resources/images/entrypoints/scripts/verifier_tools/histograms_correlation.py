import cv2
import numpy
from PIL import Image
import sys


class MetricHistogramsCorrelation:

    @staticmethod
    def compute_metrics(image1, image2):
        if image1.size != image2.size:
            raise Exception("Image sizes differ")
        opencv_image_1 = cv2.cvtColor(numpy.array(image1), cv2.COLOR_RGB2BGR)
        opencv_image_2 = cv2.cvtColor(numpy.array(image2), cv2.COLOR_RGB2BGR)
        return {
            "histograms_correlation":
                MetricHistogramsCorrelation.compare_histograms(
                    opencv_image_1,
                    opencv_image_2
                )
        }

    @staticmethod
    def get_labels():
        return ["histograms_correlation"]

    @staticmethod
    def get_number_of_pixels(image):
        height, width = image.shape[:2]
        return height * width

    @staticmethod
    def calculate_normalized_histogram(image):
        number_of_bins = 256
        channels_number = 3  # because of conversion from PIL to opencv
        histogram = cv2.calcHist([image],
                                 range(channels_number),
                                 None,
                                 [number_of_bins] * channels_number,
                                 [0, 256] * channels_number)
        cv2.normalize(histogram, histogram, 0, 256, cv2.NORM_MINMAX)
        return histogram

    @staticmethod
    def compare_histograms(image_a, image_b):
        histogram_a = MetricHistogramsCorrelation\
            .calculate_normalized_histogram(image_a)
        histogram_b = MetricHistogramsCorrelation\
            .calculate_normalized_histogram(image_b)
        result = cv2.compareHist(histogram_a, histogram_b, cv2.HISTCMP_CORREL)
        return result


def run():
    first_image = Image.open(sys.argv[1])
    second_image = Image.open(sys.argv[2])

    histograms_correlation_metric = MetricHistogramsCorrelation()

    print(
        histograms_correlation_metric.compute_metrics(first_image, second_image)
    )


if __name__ == "__main__":
    run()
