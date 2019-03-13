import os

from apps.rendering.resources.imgrepr import EXRImgRepr, \
    OpenCVImgRepr


def make_test_img(img_path, size=(10, 10), color=(255, 0, 0)):
    img = OpenCVImgRepr.empty(*size, color=color)
    img.save(img_path)


def get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def get_exr_img_repr(alt=False):
    exr = EXRImgRepr()
    exr_file = get_test_exr(alt)
    exr.load_from_file(exr_file)
    return exr
