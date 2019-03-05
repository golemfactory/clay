import math

def get_min_max_y(task_num, parts, res_y):
    if res_y % parts == 0:
        min_y = (parts - task_num) * (1.0 / parts)
        max_y = (parts - task_num + 1) * (1.0 / parts)
    else:
        ceiling_height = int(math.ceil(res_y / parts))
        ceiling_subtasks = parts - (ceiling_height * parts - res_y)
        if task_num > ceiling_subtasks:
            min_y = (parts - task_num) * (ceiling_height - 1) / res_y
            max_y = (parts - task_num + 1) * (ceiling_height - 1) / res_y
        else:
            min_y = (parts - ceiling_subtasks) * (ceiling_height - 1)
            min_y += (ceiling_subtasks - task_num) * ceiling_height
            min_y = min_y / res_y

            max_y = (parts - ceiling_subtasks) * (ceiling_height - 1)
            max_y += (ceiling_subtasks - task_num + 1) * ceiling_height
            max_y = max_y / res_y
    return min_y, max_y


class AdvanceVerificationOptions(object):
    def __init__(self):
        self.type = 'forFirst'
