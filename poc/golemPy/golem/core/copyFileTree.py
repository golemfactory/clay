import os
import shutil

def copyFileTree( src, dst, exclude = [] ):
    if not os.path.isdir( dst ):
        os.path.mkdir( dst )
    for src_dir, dirs, files in os.walk( src ):
        dst_dir = src_dir.replace(src, dst)
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        for file_ in files:
            _, ext = os.path.splitext( file_ )
            if ext in exclude:
                continue
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.copy2(src_file, dst_dir)
