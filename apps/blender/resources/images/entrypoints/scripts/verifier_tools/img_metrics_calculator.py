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
from .img_format_converter import ConvertTGAToPNG, ConvertEXRToPNG
from .imgmetrics import ImgMetrics

CROP_NAME = "scene_crop.png"
VERIFICATION_SUCCESS = "TRUE"
VERIFICATION_FAIL = "FALSE"
PKT_FILENAME = "tree35_[crr=87.71][frr=0.92].pkl"
TREE_PATH = Path(os.path.dirname(os.path.realpath(__file__))) / PKT_FILENAME
WHITE = 0
BLACK = 765
OFFSET = 30


def calculate_metrics(reference_img_path,
                      result_img_path,
                      xres,
                      yres,
                      metrics_output_filename='metrics.txt'):
    """
    This is the entry point for calculation of metrics between the
    rendered_scene and the sample(cropped_img) generated for comparison.
    :param reference_img_path:
    :param result_img_path:
    :param xres: x position of crop (left, top)
    :param yres: y position of crop (left, top)
    :param metrics_output_filename:
    :return:
    """

    cropped_img, scene_crops, rendered_scene = \
        _load_and_prepare_images_for_comparison(reference_img_path,
                                                result_img_path,
                                                xres,
                                                yres)

    best_crop = None
    best_img_metrics = None
    img_metrics = dict()
    img_metrics['Label'] = VERIFICATION_FAIL

    effective_metrics, classifier, labels, available_metrics = get_metrics()

    # First try not offset crop
    # TODO this shouldn't depend on the crops' ordering
    default_crop = scene_crops[0]
    default_metrics = compare_images(cropped_img, default_crop, available_metrics)
    try:
        label = classify_with_tree(default_metrics, classifier, labels)
        default_metrics['Label'] = label
    except Exception as e:
        print("There were errors %r" % e, file=sys.stderr)
        default_metrics['Label'] = VERIFICATION_FAIL
    if default_metrics['Label'] == VERIFICATION_SUCCESS:
        default_crop.save(CROP_NAME)
        return ImgMetrics(default_metrics).write_to_file(metrics_output_filename)
    else:
        # Try offset crops
        for crop in scene_crops[1:]:
            try:
                img_metrics = compare_images(cropped_img, crop, available_metrics)
                img_metrics['Label'] = classify_with_tree(img_metrics, classifier, labels)
            except Exception as e:
                print("There were error %r" % e, file=sys.stderr)
                img_metrics['Label'] = VERIFICATION_FAIL
            if img_metrics['Label'] == VERIFICATION_SUCCESS:
                best_img_metrics = img_metrics
                best_crop = crop
                break
        if best_crop and best_img_metrics:
            best_crop.save(CROP_NAME)
            return ImgMetrics(best_img_metrics).write_to_file(metrics_output_filename)
        else:
            # We didnt find any better match in offset crops, return the default one
            default_crop.save(CROP_NAME)
            path_to_metrics = ImgMetrics(default_metrics).write_to_file(metrics_output_filename)
            return path_to_metrics

    # This is unexpected but handle in case of errors
    stub_data = {element:-1 for element in get_labels_from_metrics(available_metrics)}
    stub_data['Label'] = VERIFICATION_FAIL
    path_to_metrics = ImgMetrics(stub_data).write_to_file(metrics_output_filename)
    return path_to_metrics


def load_classifier():
    data = decision_tree.DecisionTree.load(TREE_PATH)
    return data[0], data[1]


def classify_with_tree(metrics, classifier, feature_labels):
    features = dict()
    for label in feature_labels:
        features[label] = metrics[label]
    results = classifier.classify_with_feature_vector(features, feature_labels)
    return results[0].decode('utf-8')


def _load_and_prepare_images_for_comparison(reference_img_path,
                                            result_img_path,
                                            xres,
                                            yres):

    """
    This function prepares (i.e. crops) the rendered_scene so that it will
    fit the sample(cropped_img) generated for comparison.

    :param reference_img_path:
    :param result_img_path:
    :param xres: x position of crop (left, top)
    :param yres: y position of crop (left, top)
    :return:
    """
    rendered_scene = convert_to_png_if_needed(result_img_path)
    reference_img = convert_to_png_if_needed(reference_img_path)
    (crop_width, crop_height) = reference_img.size
    crops = get_crops(rendered_scene, xres, yres, crop_width, crop_height)
    return reference_img, crops, rendered_scene


def get_file_extension_lowercase(file_path):
    return os.path.splitext(file_path)[1][1:].lower()


def convert_to_png_if_needed(img_path):
    extension = get_file_extension_lowercase(img_path)
    name = os.path.basename(img_path)
    file_name = os.path.join("/tmp/", name)
    if extension == "exr":
        channels = OpenEXR.InputFile(img_path).header()['channels']
        if 'RenderLayer.Combined.R' in channels:
            sys.exit("There is no support for OpenEXR multilayer")
        ConvertEXRToPNG(img_path, file_name)
    elif extension == "tga":
        ConvertTGAToPNG(img_path, file_name)
    else:
        file_name = img_path
    return Image.open(file_name)


def get_crops(rendered_scene, x, y, width, height):
    offsets = itertools.product([0, -1, 1], repeat=2)
    crops = [rendered_scene.crop((x + x_offset, y + y_offset,
                                  x + width + x_offset,
                                  y + height + y_offset))
             for x_offset, y_offset in offsets]
    return crops


def get_metrics():
    classifier, feature_labels = load_classifier()
    available_metrics = ImgMetrics.get_metric_classes()
    effective_metrics = []
    for metric in available_metrics:
        for label in feature_labels:
            for label_part in metric.get_labels():
                if label_part == label and metric not in effective_metrics:
                    effective_metrics.append(metric)
    return effective_metrics, classifier, feature_labels, available_metrics


def get_labels_from_metrics(metrics):
    labels = []
    for metric in metrics:
        labels.extend(metric.get_labels())
    return labels


def compare_images(image_a, image_b, metrics) -> Dict:
    """
    This the entry point for calculating metrics between image_a, image_b
    once they are cropped to the same size.
    :param image_a:
    :param image_b:
    :return: ImgMetrics
    """

    """imageA/B are images read by: PIL.Image.open(img.png)"""
    (crop_height, crop_width) = image_a.size
    crop_resolution = str(crop_height) + "x" + str(crop_width)

    data = {"crop_resolution": crop_resolution}

    for metric_class in metrics:
        result = metric_class.compute_metrics(image_a, image_b)
        for key, value in result.items():
            data[key] = value

    return data


def convert_image_to_simple_array(image: np.ndarray) -> np.ndarray:
    """
    Function for squashing image array in to 0/1 array, which translate to
    black/white pixel
    """
    simpe_array = np.zeros((image.shape[0], image.shape[1]))
    for x, row in enumerate(image):
        for y, single_pixel in enumerate(row):
            pixel_sum = np.sum(single_pixel)
            if pixel_sum <= WHITE + OFFSET:
                simpe_array[x, y] = 0
            elif pixel_sum >= BLACK - OFFSET:
                simpe_array[x, y] = 1
            else:
                raise ValueError("Pixel incomparable. Neither black or white.")
    return simpe_array


def cut_out_crop_from_whole_image(
        yres_top: int,
        xres_left: int,
        crop: np.ndarray,
        whole_image: np.ndarray
) -> np.ndarray:
    crop_from_image = whole_image[
        yres_top:yres_top + crop.shape[0],
        xres_left:xres_left + crop.shape[1]
    ]
    return crop_from_image


def get_raw_verification(
        crop_path: str,
        subtask_img_path: str,
        crop_xres_left: int,
        crop_yres_top: int,
        metrics_output_filename: str = 'metrics.txt'
) -> str:
    croped_image = cv2.imread(crop_path)
    subtask_image = cv2.imread(subtask_img_path)

    crop_to_compare = cut_out_crop_from_whole_image(
        crop_yres_top,
        crop_xres_left,
        croped_image,
        subtask_image
    )
    is_result_positive = np.array_equal(
        convert_image_to_simple_array(croped_image),
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
    return ImgMetrics(stub_data).write_to_file(metrics_output_filename)
