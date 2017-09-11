import os
import copy


def propose_fixed_definition(task_def, data):
    # print("Hello")
    # print(task_def)
    # print(data)

    data["proposed_def"] = _get_proposed_definition(task_def, data)


def _get_proposed_definition(task_def, data):

    result = copy.deepcopy(task_def)

    try:
        _update_resolution(result, data["resolution"])
        _update_frames(result, data["frames"])
        _update_output(result, data["output_path"], data["file_format"])
        # TODO: validate and set defaults:
        #  - subtasks
        #  - compositing
        #  - timeouts
    except Exception as exc:
        return {"error": str(exc)}

    return result


def _update_resolution(result, resolution):
    width = resolution[0]
    height = resolution[1]

    # validate resolution
    list1 = [0, 0]
    list2 = result.resolution
    overlap = len(set(list1).intersection(list2)) 

    print("Resolution overlap: {}".format(overlap))

    if overlap == 0:

        if width > result.resolution[0]:
            raise Exception("width ({}) > resolution[0] ({})"
                            .format(width, result.resolution[0]))

        if height > result.resolution[1]:
            raise Exception("height ({}) > resolution[1] ({})"
                            .format(height, result.resolution[1]))

        print("Resolution checked OK")
    else:
        # set default resolution
        print("Resolution setting default")
        result.resolution = [width, height]


def _update_frames(result, frames):
    print("Updating frames")
    frames_max = frames[1]
    frames_min = frames[0]

    print(result.options.frames_string)
    # validate frames & frames_string
    if result.options.frames_string:
        frames_test = result.options.frames_string.split("-")
        max_index = len(frames_test) - 1

        if frames_max < int(frames_test[max_index]):
            raise Exception("frames_max ({}) < last(frames_test) ({})"
                            .format(frames_max, frames_test[max_index]))

        if frames_min > int(frames_test[0]):
            raise Exception("frames_min ({}) > first(frames_test) ({})"
                            .format(frames_min, frames_test[0]))
    else:
        # set default frame_string
        result.options.frames_string = "{}-{}".format(frames_min,
                                                      frames_max)

    max_frames = frames_max - frames_min + 1
    if result.options.frames:
        if max_frames < int(result.options.frames):
            raise Exception("max_frames ({}) < options.frames ({})"
                            .format(max_frames, result.options.frames))
    else:
        # set default frames
        result.options.frames = "{}".format(max_frames)


def _update_output(result, output_path, file_format):
    # validate output_format & output_file
    if result.output_format:
        # TODO: check values
        print("Validate: {}".format(result.output_format))
    else:
        # set default output_format
        # TODO: Maybe .to_upper()?
        result.output_format = file_format

    if result.output_file:
        # make sure file is writeable
        try:
            if not __is_file_writeable(result.output_file):
                raise Exception("File {} already exists"
                                .format(result.output_file))
        except IOError:
            raise Exception("Cannot open output file: {}"
                            .format(result.output_file))
        except (OSError, TypeError) as err:
            raise Exception("Output file {} is not properly set: {}"
                            .format(result.output_file, err))
    else:
        # set default output_file
        msf = os.path.normpath(result.main_scene_file)
        scene_name = msf[msf.rfind('/')+1:msf.rfind('.')]
        # TODO: find default output_dir
        output_path = "{}{}.{}".format("/tmp/",
                                       scene_name,
                                       result.output_format)

        result.output_file = output_path


def __is_file_writeable(file_path):
    # TODO: Unify apps.core.task.coretaskstate._check_output_file()
    file_exist = os.path.exists(file_path)
    with open(file_path, 'a'):
        pass
    if not file_exist:
        os.remove(file_path)
    else:
        return False
    return True
