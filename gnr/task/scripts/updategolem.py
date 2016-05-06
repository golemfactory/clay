import os
import shutil
import zlib
import pickle
from golem.core.common import get_golem_path


def update_golem():
    dst = get_golem_path()
    print dst
    src = resourcePath
    print src

    for src_dir, dirs, files in os.walk(src):
        dst_dir = src_dir.replace(src, dst)
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        for file_ in files:
            name, ext = os.path.splitext(file_)
            if ext.upper() == '.INI' or name == 'update_golem':
                continue
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.copy2(src_file, dst_dir)

    data = "Updated"
    compress = zlib.compress(data, 9)
    return {'data': [pickle.dumps((data, compress))], 'result_type': 0}


output = update_golem()
