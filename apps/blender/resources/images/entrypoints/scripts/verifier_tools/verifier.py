import json
import os
from pathlib import Path
from pprint import pprint
from typing import List, Optional, Tuple, Any, Dict

from ..render_tools import blender_render as blender
from .crop_generator import WORK_DIR, OUTPUT_DIR, FloatingPointBox, Crop, \
    Resolution
from .file_extension.matcher import get_expected_extension
from .image_metrics_calculator import calculate_metrics


def get_crop_with_id(id: int, crops: [List[Crop]]) -> Optional[Crop]:
    for crop in crops:
        if crop.id == id:
            return crop
    return None


def get_crop_rendered_data(crop_id: int, crop: Crop) -> dict:
    return {
        "id": crop.id,
        "outfilebasename": "crop" + str(crop_id) + '_',
        "borders_x": [crop.box.left, crop.box.right],
        "borders_y": [crop.box.top, crop.box.bottom]
    }


def prepare_crops(
        subtask_image_box: FloatingPointBox,
        resolution: Resolution,
        crops_count: int = 3,
        crops_borders: Optional[List[List[float]]] = None,
) -> Tuple[List[Crop], List[Dict[str, Any]]]:
    crops: List[Crop] = []
    crops_render_data = []
    if crops_borders:
        crop_id = 0
        for border in crops_borders:
            crop = Crop(
                crop_id,
                resolution,
                subtask_image_box,
                FloatingPointBox(border[0], border[1], border[2], border[3]),
            )
            crops_render_data.append(
                get_crop_rendered_data(crop_id, crop)
            )
            crops.append(crop)
            crop_id += 1
    else:
        for crop_id in range(0, crops_count):
            crop = Crop(
                crop_id,
                resolution,
                subtask_image_box,
            )
            crops_render_data.append(
                get_crop_rendered_data(crop_id, crop)
            )
            crops.append(crop)
    return crops, crops_render_data


def prepare_data_for_blender_verification(
        # pylint: disable=too-many-locals, too-many-arguments
        subtask_border: List[float],
        scene_file_path: str,
        resolution: List[int],
        samples: int,
        frames: int,
        output_format: str,
        crops_count: int = 3,
        crops_borders: Optional[List[List[float]]] = None,

) -> Tuple[List[Crop], Dict[str, Any]]:
    subtask_image_box = FloatingPointBox(
        subtask_border[0],
        subtask_border[1],
        subtask_border[2],
        subtask_border[3]
    )

    (crops, crops_render_data) = prepare_crops(
        subtask_image_box,
        Resolution(
            width=resolution[0],
            height=resolution[1],
        ),
        crops_count,
        crops_borders
    )

    blender_render_parameters = {
        "scene_file": scene_file_path,
        "resolution": resolution,
        "use_compositing": False,
        "samples": samples,
        "frames": frames,
        "start_task": 1,
        "output_format": output_format,
        "crops": crops_render_data
    }

    return crops, blender_render_parameters


def make_verdict(
        providers_result_images_paths: List[str],
        crops: List[Crop],
        reference_results: List[Dict[str, Any]],
) -> None:
    verdict = True

    for crop_data in reference_results:
        crop = get_crop_with_id(crop_data['crop']['id'], crops)

        left, top = crop.x_pixels[0], crop.y_pixels[0]
        print('borders_x: ', crop_data['crop']['borders_x'])
        print('borders_y: ', crop_data['crop']['borders_y'])
        print("left: " + str(left))
        print("top: " + str(top))

        for crop, providers_result_image_path in zip(
                crop_data['results'], providers_result_images_paths):
            crop_path = get_crop_path(OUTPUT_DIR, crop)
            results_path = calculate_metrics(
                crop_path,
                providers_result_image_path,
                left, top,
                metrics_output_filename=os.path.join(
                    OUTPUT_DIR,
                    crop_data['crop']['outfilebasename'] + "metrics.txt")
            )
            print("results_path: ", results_path)
            with open(results_path, 'r') as f:
                data = json.load(f)
            if data['Label'] != "TRUE":
                verdict = False

    with open(os.path.join(OUTPUT_DIR, 'verdict.json'), 'w') as f:
        json.dump({'verdict': verdict}, f)


def get_crop_path(parent: str, filename: str) -> str:
    """
    Attempts to get the path to a crop file. If no file exists under the
    provided path, the original file extension is replaced with an expected
    one.
    :param parent: directory where crops are located.
    :param filename: the expected crop file name, based on the file extension
    provided in verifier parameters.
    :return: path to the requested crop file, possibly with a different file
    extension.
    :raises FileNotFoundError if no matching crop file could be found.
    """
    crop_path = Path(parent, filename)

    if crop_path.exists():
        return str(crop_path)

    expected_extension = get_expected_extension(crop_path.suffix)
    expected_path = crop_path.with_suffix(expected_extension)

    if expected_path.exists():
        return str(expected_path)

    raise FileNotFoundError(f'Could not find crop file. Paths checked:'
                            f'{crop_path}, {expected_path}')


def verify(  # pylint: disable=too-many-arguments
        subtask_file_paths: List[str],
        subtask_border: List[float],
        scene_file_path: str,
        resolution: List[int],
        samples: int,
        frames: int,
        output_format: str,
        crops_count: int = 3,
        crops_borders: Optional[List[List[float]]] = None,
) -> None:
    """
    Function will verify image with crops rendered from given blender
    scene file.

    subtask_file_paths - path (or paths if there was more than one frame)
                         to image file, that will be compared against crops
    subtask_border - [left, top, right, bottom] float decimal values
                     representing image localization in whole blender scene
    scene_file_path - path to blender scene file
    resolution - resolution at which given subtask was rendered
                 (crop will be rendered with exactly same parameters)
    samples - samples at which given subtask was rendered
    frames - number of frames that are present in subtasks
    output_format - output format of rendered crops
    crops_count - number of randomly generated crops, (default 3)
    crops_borders - list of [left, top, right, bottom] float decimal
                    values lists, representing crops borders
                    those will be used instead of random crops, if present.
    """
    mounted_paths = dict()
    mounted_paths["WORK_DIR"] = WORK_DIR
    mounted_paths["OUTPUT_DIR"] = OUTPUT_DIR

    (crops,
     blender_render_parameters) = prepare_data_for_blender_verification(
        subtask_border,
        scene_file_path,
        resolution,
        samples,
        frames,
        output_format,
        crops_count,
        crops_borders
    )
    print("blender_render_params:")
    pprint(blender_render_parameters)
    save_params(blender_render_parameters, "blender_render_params.json",
                mounted_paths)

    results = blender.render(blender_render_parameters, mounted_paths)

    print("results:")
    pprint(results)

    make_verdict(subtask_file_paths, crops, results)


def convert_float32_to_double(params: dict):
    new_params = params.copy()
    crops_array = new_params['crops']

    for crop in crops_array:
        # value.item() converts numpy type to native Python type
        crop['borders_x'] = [value.item() for value in crop['borders_x']]
        crop['borders_y'] = [value.item() for value in crop['borders_y']]

    return new_params


def save_params(params: dict, filename: str, mounted_paths: dict):
    new_params = convert_float32_to_double(params)

    path = os.path.join(mounted_paths["WORK_DIR"], filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(new_params, f)
