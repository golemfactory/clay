import io
import os
import json
import numpy as np
import sys


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        print("There were obj %r" % obj, file=sys.stderr)

        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.float32):
            return float(obj)
        elif isinstance(obj, np.float64):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return obj.__dict__


class ImgageMetrics:
    """
    ImgageMetrics is a structure for storing img comparison metric.
    methods write/load are to facilitate file movement to/from docker.
    """

    def __init__(self, dictionary=None):
        self.ssim = None
        self.reference_variance = None
        self.image_variance = None
        self.ref_edge_factor = None
        self.comp_edge_factor = None
        self.edge_difference = None
        self.wavelet_sym2_base = None
        self.wavelet_sym2_low = None
        self.wavelet_sym2_mid = None
        self.wavelet_sym2_high = None
        self.wavelet_db4_base = None
        self.wavelet_db4_low = None
        self.wavelet_db4_mid = None
        self.wavelet_db4_high = None
        self.wavelet_haar_base = None
        self.wavelet_haar_low = None
        self.wavelet_haar_mid = None
        self.wavelet_haar_high = None
        self.wavelet_haar_freq_x1 = None
        self.wavelet_haar_freq_x2 = None
        self.wavelet_haar_freq_x3 = None
        self.histograms_correlation = None
        self.max_x_mass_center_distance = None
        self.max_y_mass_center_distance = None
        self.crop_resolution = None
        self.variance_difference = None

        # ensure that the keys are correct
        keys = ImgageMetrics.get_metric_names()
        keys.append('Label')

        for key in keys:
            if key not in dictionary:
                raise KeyError("missing metric:" + key)

        # read into ImgMetrics object
        for key in dictionary:
            setattr(self, key, dictionary[key])

    @staticmethod
    def get_metric_classes():
        from . import (
            ssim,
            psnr,
            variance,
            edges,
            wavelet,
            histograms_correlation,
            mass_center_distance,
        )
        available_metrics = [
            ssim.MetricSSIM,
            psnr.MetricPSNR,
            variance.ImageVariance,
            edges.MetricEdgeFactor,
            wavelet.MetricWavelet,
            histograms_correlation.MetricHistogramsCorrelation,
            mass_center_distance.MetricMassCenterDistance
        ]

        return available_metrics

    @staticmethod
    def get_metric_names():
        metric_names = []
        for metric_class in ImgageMetrics.get_metric_classes():
            metric_names = metric_names + metric_class.get_labels()
        return metric_names

    def to_json(self):
        str_ = json.dumps(self,
                          cls=MyEncoder,
                          indent=4,
                          sort_keys=True,
                          separators=(',', ': '),
                          ensure_ascii=False)
        return str_

    def write_to_file(self, file_name='img_metrics.txt'):
        dir_path = os.path.dirname(os.path.realpath(__file__))
        file_path = os.path.join(dir_path, file_name)

        data = self.to_json()
        with io.open(file_path, 'w', encoding='utf-8') as f:
            f.write(data)

        return file_path

    @classmethod
    def load_from_file(cls, file_path=None):
        with open(file_path, 'r') as f:
            dictionary = json.load(f)
            image_metrics = cls(dictionary)
            return image_metrics
