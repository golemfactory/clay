import itertools
import logging
import os
import sys
from typing import Dict

from PIL import Image

import OpenEXR

from . import decision_tree
from .img_format_converter import ConvertTGAToPNG, ConvertEXRToPNG
from .imgmetrics import ImgMetrics


logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                    format='%(levelname)-8s [%(name)-35s] %(message)s')
logger = logging.getLogger(__name__)


CROP_NAME = "scene_crop.png"
VERIFICATION_SUCCESS = "TRUE"
VERIFICATION_FAIL = "FALSE"
TREE_PATH = "/golem/scripts/tree35_[crr=87.71][frr=0.92].pkl"


def calculate_metrics(reference_img_path,
                      result_img_path,
                      base_coord_x,
                      base_coord_y,
                      metrics_output_filename='metrics.txt'):
    """
    This is the entry point for calculation of metrics between the
    rendered_scene and the sample(cropped_img) generated for comparison.
    :param reference_img_path:
    :param result_img_path:
    :param base_coord_x: x position of crop (left, top)
    :param base_coord_y: y position of crop (left, top)
    :param metrics_output_filename:
    :return:
    """
    metrics_path = metrics_output_filename
    cropped_img, scene_crops, _rendered_scene = \
        _load_and_prepare_images_for_comparison(reference_img_path,
                                                result_img_path,
                                                base_coord_x,
                                                base_coord_y)

    _effective_metrics, classifier, labels, available_metrics = get_metrics()
    default_metrics = {'Label': VERIFICATION_FAIL}
    for crop_offset, crop_image in scene_crops.items():
        try:
            crop_coords = (base_coord_x + crop_offset[0], base_coord_y +
                           crop_offset[1])
            logger.debug('Trying to match crop {}[offset = {}]'
                         .format(crop_coords, crop_offset))
            metrics = compare_images(cropped_img, crop_image, available_metrics)
            result_label = classify_with_tree(metrics, classifier, labels)
            if crop_offset == (0, 0):
                default_metrics.update(metrics)
            if result_label == VERIFICATION_SUCCESS:
                metrics['Label'] = VERIFICATION_SUCCESS
                logger.info('Crop {}[offset={}] was verified successfully'
                            .format(crop_coords, crop_offset))
                crop_image.save(CROP_NAME)
                return ImgMetrics(metrics).write_to_file(metrics_path)
            logger.info('Crop {}[offset={}] was verified unsuccessfully'
                        .format(crop_coords, crop_offset))

        except Exception as e:
            logger.exception('Error has occurred trying to match crop '
                             'offset={}]'.format(crop_offset), e)
    logger.warning('No crop satisfied verification process. Returning metrics'
                   'for default one [coordinates={}]'.format((base_coord_x,
                                                              base_coord_y)))

    scene_crops.get((0, 0)).save(CROP_NAME)
    return ImgMetrics(default_metrics).write_to_file(metrics_path)


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
                                            result_img_path, xres, yres):
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


def create_crop(rendered_scene, x, y, x_offset, y_offset, width, height):
    return rendered_scene.crop((x + x_offset, y + y_offset,
                                x + width + x_offset, y + height + y_offset))


def get_crops(rendered_scene, x, y, width, height):
    offsets = itertools.product([0, -1, 1], repeat=2)
    crops = {(x_offset, y_offset):  create_crop(rendered_scene, x, y, x_offset,
                                                y_offset, width, height)
             for x_offset, y_offset in offsets}
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
        labels.extend(metric.get_lables())
    return labels


def compare_images(image_a, image_b, metrics) -> Dict:
    """
    This the entry point for calculating metrics between image_a, image_b
    once they are cropped to the same size.
    :param image_a:
    :param image_b:
    :param metrics:
    :return: ImgMetrics
    """
    # imageA/B are images read by: PIL.Image.open(img.png)
    (crop_height, crop_width) = image_a.size
    crop_resolution = str(crop_height) + "x" + str(crop_width)

    data = {"crop_resolution": crop_resolution}

    for metric_class in metrics:
        result = metric_class.compute_metrics(image_a, image_b)
        for key, value in result.items():
            data[key] = value

    return data
