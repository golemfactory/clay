import cv2
import itertools
import os
import sys
import numpy as np
from pathlib import Path
from typing import Dict

import OpenEXR
from PIL import Image

from . import decision_tree
from .image_format_converter import convert_tga_to_png, convert_exr_to_png
from .imgmetrics import ImgMetrics


# todo review: refer to crops as "providers_result_crop" and "reference_crop",
#  now it's not clear which one was cut out from image and which one was
#  rendered locally. Analogically use "providers_result_image" instead of
#  "rendered_scene". Variables which are pointing to uncropped provider's result
#  should contain this information in name ("providers_result_uncropped", for
#  instance)


# todo review: rename this variable and the file so they indicate which
#  (reference or provider's result) crop they are
CROP_NAME = "scene_crop.png"
VERIFICATION_SUCCESS = "TRUE"
VERIFICATION_FAIL = "FALSE"
PKT_FILENAME = "tree35_[crr=87.71][frr=0.92].pkl"
TREE_PATH = Path(os.path.dirname(os.path.realpath(__file__))) / PKT_FILENAME
# todo review: this is image_metrics_calculator.py, it's not a good place for
#  the alternative verification method used only in tests.
WHITE = 0
BLACK = 765
OFFSET = 30


def calculate_metrics(
        reference_crop_path,
        providers_result_image,
        top_left_corner_x,
        top_left_corner_y,
        metrics_output_filename='metrics.txt'
):
    # todo review: remove the workaround instead of commenting it
    """
    This is the entry point for calculation of metrics between the
    rendered_scene and the sample(cropped_image) generated for comparison.
    :param reference_crop_path:
    :param providers_result_image:
    :param top_left_corner_x: x position of crop (left, top)
    :param top_left_corner_y: y position of crop (left, top)
    :param metrics_output_filename:
    :return:
    """
    (cropped_image, scene_crops) = \
        _load_and_prepare_images_for_comparison(
            reference_crop_path,
            providers_result_image,
            top_left_corner_x,
            top_left_corner_y
        )
    image_metrics = dict()
    image_metrics['Label'] = VERIFICATION_FAIL

    (classifier, labels, available_metrics) = get_metrics()

    # TODO this shouldn't depend on the crops' ordering
    providers_result_crop = scene_crops[0]
    print(f"default_crop: {providers_result_crop.getbbox()}")
    default_metrics = compare_images(
        cropped_image,
        providers_result_crop,
        available_metrics
    )
    try:
        label = classify_with_tree(default_metrics, classifier, labels)
        default_metrics['Label'] = label
    except Exception as e:
        print("There were errors %r" % e, file=sys.stderr)
        default_metrics['Label'] = VERIFICATION_FAIL

    providers_result_crop.save(CROP_NAME)
    return ImgMetrics(default_metrics).write_to_file(
        metrics_output_filename
    )


def load_classifier():
    classifier, feature_labels = decision_tree.DecisionTree.load(TREE_PATH)
    return classifier, feature_labels


def classify_with_tree(metrics, classifier, feature_labels):
    features = dict()
    for label in feature_labels:
        features[label] = metrics[label]
    results = classifier.classify_with_feature_vector(features, feature_labels)
    return results[0].decode('utf-8')


# todo review: this should generate 1 crop instead of 9
def _load_and_prepare_images_for_comparison(
        reference_crop_path,
        result_image_path,
        top_left_corner_x,
        top_left_corner_y
):
    """
    This function prepares (i.e. crops) the rendered_scene so that it will
    fit the sample(cropped_image) generated for comparison.

    :param reference_crop_path:
    :param result_image_path:
    :param top_left_corner_x: x position of crop (left, top)
    :param top_left_corner_y: y position of crop (left, top)
    :return:
    """
    rendered_scene = convert_to_png_if_needed(result_image_path)
    # todo review: rename to "reference_crop"
    reference_image = convert_to_png_if_needed(reference_crop_path)
    (crop_width, crop_height) = reference_image.size
    print(f"top_left_corner_x={top_left_corner_x}, top_left_corner_y={top_left_corner_y}, width={crop_width}, height={crop_height}")
    crops = get_providers_result_crop(rendered_scene, top_left_corner_x, top_left_corner_y, crop_width, crop_height)
    return reference_image, crops


def get_file_extension_lowercase(file_path):
    return os.path.splitext(file_path)[1][1:].lower()


def convert_to_png_if_needed(image_path):
    extension = get_file_extension_lowercase(image_path)
    name = os.path.basename(image_path)
    file_name = os.path.join("/tmp/", name)
    if extension == "exr":
        channels = OpenEXR.InputFile(image_path).header()['channels']
        if 'RenderLayer.Combined.R' in channels:
            sys.exit("There is no support for OpenEXR multilayer")
        convert_exr_to_png(image_path, file_name)
    elif extension == "tga":
        convert_tga_to_png(image_path, file_name)
    else:
        file_name = image_path
    return Image.open(file_name)


# todo review: should return only one crop
def get_providers_result_crop(rendered_scene, x, y, width, height):
    offsets = itertools.product([0, -1, 1], repeat=2)
    crops = [rendered_scene.crop((x + x_offset, y + y_offset,
                                  x + width + x_offset,
                                  y + height + y_offset))
             for x_offset, y_offset in offsets]
    return crops


def get_metrics():
    classifier, feature_labels = load_classifier()
    available_metrics = ImgMetrics.get_metric_classes()
    # todo review: effective_metrics isn't used after filling it with values
    #  in the loops below
    effective_metrics = []
    for metric in available_metrics:
        for label in feature_labels:
            for label_part in metric.get_labels():
                if label_part == label and metric not in effective_metrics:
                    effective_metrics.append(metric)
    return classifier, feature_labels, available_metrics


def get_labels_from_metrics(metrics):
    labels = []
    for metric in metrics:
        labels.extend(metric.get_labels())
    return labels


# todo review: docstring is missing "metrics" parameter
def compare_images(image_a, image_b, metrics) -> Dict:
    """
    This the entry point for calculating metrics between image_a, image_b
    once they are cropped to the same size.
    :param image_a:
    :param image_b:
    :return: ImgMetrics
    """

    """imageA/B are images read by: PIL.Image.open(image.png)"""
    (crop_height, crop_width) = image_a.size
    crop_resolution = str(crop_height) + "x" + str(crop_width)

    data = {"crop_resolution": crop_resolution}

    for metric_class in metrics:
        result = metric_class.compute_metrics(image_a, image_b)
        for key, value in result.items():
            data[key] = value

    return data


# todo review: functions below are used only in tests, they should be moved to
#  a file in the tests directory (check comment in line 36)
# todo review: function's name should describe what it actually does, so it
#  should contain information about squashing pixel values to black and white
def convert_image_to_simple_array(image: np.ndarray) -> np.ndarray:
    """
    Function for squashing image array in to 0/1 array, which translate to
    black/white pixel
    """
    simple_array = np.zeros((image.shape[0], image.shape[1]))
    for x, row in enumerate(image):
        for y, single_pixel in enumerate(row):
            pixel_sum = np.sum(single_pixel)
            if pixel_sum <= WHITE + OFFSET:
                simple_array[x, y] = 0
            elif pixel_sum >= BLACK - OFFSET:
                simple_array[x, y] = 1
            else:
                raise ValueError("Pixel incomparable. Neither black or white.")
    return simple_array


# todo review: why are you implementing another function for cropping instead of
#  using previously written functions used for real verification?
def cut_out_crop_from_whole_image(
        top_left_corner_x: int,
        top_left_corner_y: int,
        crop: np.ndarray,
        whole_image: np.ndarray
) -> np.ndarray:
    crop_from_image = whole_image[
        top_left_corner_y:top_left_corner_y + crop.shape[0],
        top_left_corner_x:top_left_corner_x + crop.shape[1]
    ]
    return crop_from_image


def get_raw_verification(
        crop_path: str,
        subtask_image_path: str,
        crop_xres_left: int,
        crop_yres_top: int,
        metrics_output_filename: str = 'metrics.txt'
) -> str:
    cropped_image = cv2.imread(crop_path)
    subtask_image = cv2.imread(subtask_image_path)

    crop_to_compare = cut_out_crop_from_whole_image(
        crop_xres_left,
        crop_yres_top,
        cropped_image,
        subtask_image
    )
    is_result_positive = np.array_equal(
        convert_image_to_simple_array(cropped_image),
        convert_image_to_simple_array(crop_to_compare)
    )
    available_metrics = ImgMetrics.get_metric_classes()
    stub_data = {
        element: 'unavailable' for element in
        get_labels_from_metrics(available_metrics)
    }
    if is_result_positive:
        stub_data['Label'] = VERIFICATION_SUCCESS
    else:
        stub_data['Label'] = VERIFICATION_FAIL
    # todo review: writing to file won't be necessary after moving raw
    #  verification to tests
    return ImgMetrics(stub_data).write_to_file(metrics_output_filename)
