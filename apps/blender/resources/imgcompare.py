from apps.rendering.resources.imgrepr import load_img


def check_size(file_, res_x, res_y):
    # allow +/-1 difference in y size - workaround for blender inproperly rounding floats
    img = load_img(file_)
    if img is None:
        return False
    img_x, img_y = img.get_size()
    return (img_x == res_x) and (abs(img_y - res_y) <= 1)
