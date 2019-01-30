import os
import sys
import pickle
from typing import Dict

import numpy as np
import OpenEXR
from PIL import Image

import decision_tree
from img_format_converter import \
    ConvertTGAToPNG, ConvertEXRToPNG
from imgmetrics import \
    ImgMetrics

CROP_NAME = "/golem/output/scene_crop.png"
VERIFICATION_SUCCESS = "TRUE"
VERIFICATION_FAIL = "FALSE"
TREE_PATH = "/golem/scripts_verifier/tree35_[crr=87.71][frr=0.92].pkl"

def compare_crop_window(cropped_img_path,
                        rendered_scene_path,
                        xres, yres,
                        output_filename_path='metrics.txt'):
    """
    This is the entry point for calculation of metrics between the
    rendered_scene and the sample(cropped_img) generated for comparison.
    :param cropped_img_path:
    :param rendered_scene_path:
    :param xres: x position of crop (left, top)
    :param yres: y position of crop (left, top)
    :param output_filename_path:
    :return:
    """

    cropped_img, scene_crops, rendered_scene = \
        _load_and_prepare_img_for_comparison(
            cropped_img_path,
            rendered_scene_path,
            xres, yres)

    best_crop = None
    best_img_metrics = None
    img_metrics = dict()
    img_metrics['Label'] = VERIFICATION_FAIL

    effective_metrics, classifier, labels, available_metrics = get_metrics()

    # First try not offset crop

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
        return ImgMetrics(default_metrics).write_to_file(output_filename_path)
    else:
        # Try offsete crops
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
            return ImgMetrics(best_img_metrics).write_to_file(output_filename_path)
        else:
            # We didnt find any better match in offset crops, return the default one
            default_crop.save(CROP_NAME)
            path_to_metrics = ImgMetrics(default_metrics).write_to_file(output_filename_path)
            return path_to_metrics

    #This is unexpected but handle in case of errors
    stub_data = {element:-1 for element in get_labels_from_metrics(available_metrics)}
    stub_data['Label'] = VERIFICATION_FAIL
    path_to_metrics = ImgMetrics(stub_data).write_to_file(output_filename_path)
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

def _load_and_prepare_img_for_comparison(cropped_img_path,
                                         rendered_scene_path,
                                         xres, yres):

    """
    This function prepares (i.e. crops) the rendered_scene so that it will
    fit the sample(cropped_img) generated for comparison.

    :param cropped_img_path:
    :param rendered_scene_path:
    :param xres: x position of crop (left, top)
    :param yres: y position of crop (left, top)
    :return:
    """
    rendered_scene = None
    # if rendered scene has .exr format need to convert it for .png format
    if os.path.splitext(rendered_scene_path)[1] == ".exr":
        check_input = OpenEXR.InputFile(rendered_scene_path).header()[
            'channels']
        if 'RenderLayer.Combined.R' in check_input:
            sys.exit("There is no support for OpenEXR multilayer")
        file_name = "/tmp/scene.png"
        ConvertEXRToPNG(rendered_scene_path, file_name)
        rendered_scene = Image.open(file_name)
    elif os.path.splitext(rendered_scene_path)[1] == ".tga":
        file_name = "/tmp/scene.png"
        ConvertTGAToPNG(rendered_scene_path, file_name)
        rendered_scene = Image.open(file_name)
    else:
        rendered_scene = Image.open(rendered_scene_path)

    cropped_img = Image.open(cropped_img_path)
    (crop_width, crop_height) = cropped_img.size

    crops = get_crops(rendered_scene, xres, yres, crop_width, crop_height)

    return cropped_img, crops, rendered_scene


def get_crops(input, x, y, width, height):
    crops = []

    scene_crop = input.crop((x, y, x + width, y + height))

    crops.append(scene_crop)

    scene_crop_left = input.crop((x-1, y, x + width-1, y + height))

    crops.append(scene_crop_left)

    scene_crop_left_up = input.crop((x-1, y-1, x + width-1, y + height-1))

    crops.append(scene_crop_left_up)

    scene_crop_up = input.crop((x, y-1, x + width, y + height-1))

    crops.append(scene_crop_up)

    scene_crop_up_right = input.crop((x+1, y-1, x + width+1, y + height-1))

    crops.append(scene_crop_up_right)

    scene_crop_right = input.crop((x+1, y, x + width+1, y + height))

    crops.append(scene_crop_right)

    scene_crop_down_right = input.crop((x+1, y+1, x + width+1, y + height+1))

    crops.append(scene_crop_down_right)

    scene_crop_down = input.crop((x, y+1, x + width, y + height+1))

    crops.append(scene_crop_down)

    scene_crop_down_left = input.crop((x-1, y+1, x + width-1, y + height+1))

    crops.append(scene_crop_down_left)

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
