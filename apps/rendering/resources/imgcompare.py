from apps.rendering.resources.imgrepr import load_img


def check_size(file_, res_x, res_y):
    img = load_img(file_)
    if img is None:
        return False
    return img.get_size() == (res_x, res_y)