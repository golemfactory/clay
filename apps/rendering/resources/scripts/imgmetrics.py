import io
import os
import json


class ImgMetrics:
    """
    ImgMetrics is a structure for storing img comparison metric.
    methods write/load are to facilitate file movement to/from docker.
    """

    def __init__(self, dictionary=None):
        self.imgCorr = None  # for intellisense
        self.SSIM_normal = None
        self.MSE_normal = None
        self.SSIM_canny = None
        self.MSE_canny = None
        self.SSIM_wavelet = None
        self.MSE_wavelet = None
        self.crop_resolution = None
        # ensure that the keys are correct
        keys = ['imgCorr',
                'SSIM_normal', 'MSE_normal',
                'SSIM_canny', 'MSE_canny',
                'SSIM_wavelet', 'MSE_wavelet',
                'crop_resolution']

        for key in keys:
            if key not in dictionary:
                raise KeyError("missing metric:" + key)

        # read into ImgMetrics object
        for key in dictionary:
            setattr(self, key, dictionary[key])

    def to_json(self):
        str_ = json.dumps(self,
                          default=lambda o: o.__dict__,
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
            img_metrics = cls(dictionary)
            return img_metrics
