import os
import sys
from pathlib import Path
from typing import Dict

import OpenEXR
from PIL import Image

from . import decision_tree
from .image_format_converter import convert_tga_to_png, convert_exr_to_png
from .image_metrics import ImgageMetrics


PROVIDER_RESULT_CROP_NAME_PREFIX = "fragment_corresponding_to_"
VERIFICATION_SUCCESS = "TRUE"
VERIFICATION_FAIL = "FALSE"
PKT_FILENAME = "tree35_[crr=87.71][frr=0.92].pkl"
TREE_PATH = Path(os.path.dirname(os.path.realpath(__file__))) / PKT_FILENAME


def calculate_metrics(
        reference_crop_path,
        providers_result_image_path,
        top_left_corner_x,
        top_left_corner_y,
        metrics_output_filename='metrics.txt'
):
    """
    This is the entry point for calculation of metrics between the
    rendered_scene and the sample(cropped_image) generated for comparison.
    :param reference_crop_path:
    :param providers_result_image_path:
    :param top_left_corner_x: x position of crop (left, top)
    :param top_left_corner_y: y position of crop (left, top)
    :param metrics_output_filename:
    :return:
    """
    (cropped_image, providers_result_crop) = \
        _load_and_prepare_images_for_comparison(
            reference_crop_path,
            providers_result_image_path,
            top_left_corner_x,
            top_left_corner_y
        )
    image_metrics = dict()
    image_metrics['Label'] = VERIFICATION_FAIL

    (classifier, labels, available_metrics) = get_metrics()

    print(f"providers_result_crop: {providers_result_crop.getbbox()}")
    compare_metrics = compare_images(
        cropped_image,
        providers_result_crop,
        available_metrics
    )
    try:
        label = classify_with_tree(compare_metrics, classifier, labels)
        compare_metrics['Label'] = label
    except Exception as e:
        print("There were errors %r" % e, file=sys.stderr)
        compare_metrics['Label'] = VERIFICATION_FAIL
    providers_result_crop.save(
        _generate_path_for_providers_result_crop(reference_crop_path)
    )
    return ImgageMetrics(compare_metrics).write_to_file(
        metrics_output_filename
    )


def _generate_path_for_providers_result_crop(reference_crop_path):
    return '{0}{1}.png'.format(
        PROVIDER_RESULT_CROP_NAME_PREFIX,
        os.path.splitext(os.path.basename(reference_crop_path))[0],
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


def _load_and_prepare_images_for_comparison(
        reference_crop_path,
        result_image_path,
        top_left_corner_x,
        top_left_corner_y
):
    """
    This function prepares (i.e. crops) the providers_result_image so that it
    will fit the sample(cropped_image) generated for comparison.

    :param reference_crop_path:
    :param result_image_path:
    :param top_left_corner_x: x position of crop (left, top)
    :param top_left_corner_y: y position of crop (left, top)
    :return:
    """
    print(f"result_image_path = {result_image_path}")
    print(f"reference_crop_path = {reference_crop_path}")
    providers_result_image = convert_to_png_if_needed(result_image_path)
    reference_crop = convert_to_png_if_needed(reference_crop_path)
    (crop_width, crop_height) = reference_crop.size
    print(
        f"top_left_corner_x={top_left_corner_x}, "
        f"top_left_corner_y={top_left_corner_y}, "
        f"width={crop_width}, height={crop_height}"
    )
    provider_crop = get_providers_result_crop(
        providers_result_image,
        top_left_corner_x,
        top_left_corner_y,
        crop_width,
        crop_height
    )
    return reference_crop, provider_crop


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


def get_providers_result_crop(providers_result_image, x, y, width, height):
    return providers_result_image.crop((x, y, x + width, y + height))


def get_metrics():
    classifier, feature_labels = load_classifier()
    available_metrics = ImgageMetrics.get_metric_classes()
    # todo review: DONE IN DOCS
    #  effective_metrics isn't used after filling it with values
    #  in the loops below
    effective_metrics = []
    for metric in available_metrics:
        for label in feature_labels:
            for label_part in metric.get_labels():
                if label_part == label and metric not in effective_metrics:
                    effective_metrics.append(metric)
    return (classifier, feature_labels, available_metrics)


def get_labels_from_metrics(metrics):
    labels = []
    for metric in metrics:
        labels.extend(metric.get_labels())
    return labels


def compare_images(image_a, image_b, metrics) -> Dict:
    """
    This the entry point for calculating metrics between image_a, image_b
    once they are cropped to the same size.
    """

    # imageA/B are images read by: PIL.Image.open(image.png)
    (crop_height, crop_width) = image_a.size
    crop_resolution = str(crop_height) + "x" + str(crop_width)

    data = {"crop_resolution": crop_resolution}

    for metric_class in metrics:
        result = metric_class.compute_metrics(image_a, image_b)
        for key, value in result.items():
            data[key] = value

    return data
