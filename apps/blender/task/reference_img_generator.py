import os
import random
import math
import numpy as np

import os
import subprocess

from apps.blender.resources.scenefileeditor import generate_blender_crop_file

BLENDER = "blender"

# todo GG this is from CP, shall run in docker
def exec_cmd(cmd):
    pc = subprocess.Popen(cmd)
    return pc.wait()


def generate_blenderimage(scene_file, output=None, script_file=None, frame=1):
    """
    Generate image from Blender scene file (.blend)
    :param string scene_file: path to blender scene file (.blend)
    :param string|None output: path to output image. If set to None than
    default name will be set
    :param string|None script_file|None: add path to blender script that
    defines potential modification of scene
    :param int frame: number of frame that should be render. Default is set to 1
    """
    cmd = [BLENDER, "-b", scene_file, "-y"]
    previous_wd = os.getcwd()
    os.chdir(os.path.dirname(os.path.abspath(scene_file)))
    if script_file:
        cmd.append("-P")
        cmd.append(script_file)
    if output:
        outbase, ext = os.path.splitext(output)
        cmd.append("-o")
        cmd.append(output)
        print(ext)
        print(ext[1:])
        if ext:
            cmd.append("-F")
            cmd.append(ext[1:].upper())
    cmd.append("-noaudio")
    cmd.append("-f")
    cmd.append(str(frame))
    print(cmd)
    exec_cmd(cmd)
    os.chdir(previous_wd)


def generate_img_with_params(scene_file, script_name="tmp.py", xres=800,
                             yres=600, crop=None, use_compositing=False,
                             output=None, frame=1):
    """
    Generate image from blender scene file(.blend) with changed parameters
    :param string scene_file: path to blender scene file (.blend)
    :param string script_name: name of the new script file that will be used
     for scene modification. It should be just name of the file and not path,
     because it will be saved in main scene file directory.
    :param int xres: new resolution in pixels
    :param int yres: new resolution in pixels
    :param list|None crop: values describing render region that range from
    min (0) to max (1) in order xmin, xmax, ymin,ymax. (0,0) is bottom left. If
    is set to None then full window will be rendered
    :param string output: path to final saved image. If this value
    is set to None, then default value will be used.
    """

    if crop is None:
        crop = [0, 1, 0, 1]

    crop_file_src = generate_blender_crop_file([xres, yres], [crop[0], crop[1]],
                                           [crop[2], crop[3]], use_compositing)

    scene_dir = os.path.dirname(os.path.abspath(scene_file))
    new_scriptpath = os.path.join(scene_dir, script_name)

    with open(new_scriptpath, 'w') as f:
        f.write(crop_file_src)

    generate_blenderimage(scene_file, output, new_scriptpath, frame)


def generate_random_crop(scene_file, crop_scene_size, crop_count, resolution, rendered_scene, scene_format,test_number):
    # Get resolution from rendered scene
    # Get border limits from crop_scene_size
    resolution_y, resolution_x = rendered_scene.shape[:2]
    whole_scene_resolution_x, whole_scene_resolution_y = resolution
    crop_scene_xmin, crop_scene_xmax, crop_scene_ymin, crop_scene_ymax = crop_scene_size
    crop_size_x = 0
    crop_size_y = 0
    # check resolution, make sure that cropp is greather then 8px.
    while(crop_size_x * whole_scene_resolution_x < 8):
        crop_size_x += 0.01
    while(crop_size_y * whole_scene_resolution_y < 8):
        crop_size_y += 0.01
    blender_crops = []
    blender_crops_pixel = []

    # second test, with larger crop window
    if test_number == 2:
        crop_size_x += 0.01
        crop_size_y += 0.01


    # Randomisation cX and Y coordinate to render crop window
    # Blender cropping window from bottom left. Cropped window pixels 0,0 are in top left
    for crop in range(crop_count):
        x_difference = round((crop_scene_xmax - crop_size_x)*100, 2)
        x_min = random.randint(crop_scene_xmin * 100, x_difference) / 100
        x_max = round(x_min + crop_size_x, 2)
        y_difference = round((crop_scene_ymax - crop_size_y)*100, 2)
        y_min = random.randint(crop_scene_ymin * 100, y_difference) / 100
        y_max = round(y_min + crop_size_y, 2)
        blender_crop = x_min, x_max, y_min, y_max
        blender_crops.append(blender_crop)
        x_pixel_min = math.floor(np.float32(whole_scene_resolution_x) * np.float32(x_min))
        y_pixel_max = math.floor(np.float32(whole_scene_resolution_y) * np.float32(y_max))
        x_pixel_min = x_pixel_min - math.floor(np.float32(crop_scene_xmin) * np.float32(whole_scene_resolution_x))
        y_pixel_min = math.floor(np.float32(crop_scene_ymax) * np.float32(whole_scene_resolution_y)) - y_pixel_max
        crop_pixel = x_pixel_min, y_pixel_min
        blender_crops_pixel.append(crop_pixel)
        print(str(crop+1)+'.', x_min, x_max, y_min, y_max, x_pixel_min, y_pixel_min)

    blender_crops_path = []
    crop_count = 1
    # Rendering crop windows with all parametrs
    for blender_crop in blender_crops:
        output = "/tmp/" + str(crop_count)
        generate_img_with_params(
            scene_file=scene_file,
            xres=whole_scene_resolution_x,
            yres=whole_scene_resolution_y,
            crop=blender_crop,
            output=output
        )

        output += "0001" + str(scene_format)
        if not os.path.isfile(output):
            raise ValueError('Scene to compare have diffrent format then in .blend file!')
        blender_crops_path.append(output)
        crop_count += 1
    print("xress: " + str(whole_scene_resolution_x) + " yress: " + str(whole_scene_resolution_y) +
        " crop_size_x: " + str(crop_size_x) + ' crop_size_y ' + str(crop_size_y))
    return blender_crops_pixel, blender_crops_path, blender_crops
