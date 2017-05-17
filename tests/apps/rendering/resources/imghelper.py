import os

from PIL import Image

from apps.rendering.resources.imgrepr import EXRImgRepr, PILImgRepr


def make_test_img(img_path, size=(10, 10), color=(255, 0, 0)):
    img = Image.new('RGB', size, color)
    img.save(img_path)
    img.close()


def get_test_exr(alt=False):
    if not alt:
        filename = 'testfile.EXR'
    else:
        filename = 'testfile2.EXR'

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


def get_pil_img_repr(path, size=(10, 10), color=(255, 0, 0)):
    make_test_img(path, size, color)
    p = PILImgRepr()
    p.load_from_file(path)
    return p


def get_exr_img_repr(alt=False):
    exr = EXRImgRepr()
    exr_file = get_test_exr(alt)
    exr.load_from_file(exr_file)
    return exr
