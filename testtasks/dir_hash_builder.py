'''
Calculates SHA-1 checksum of the given directory's content
'''
from execution_time_measure import *
import hashlib
import os


def get_current_directory(_file):
    current_directory = os.path.dirname(os.path.abspath(_file))
    if not os.path.exists(current_directory):
        return "-1"
    else:
        return current_directory


def get_hash_of_dir(directory, verbose=0):
    import hashlib, os
    SHAhash = hashlib.sha1()
    if not os.path.exists (directory):
        return "-1"
        
    try:
        for root, dirs, files in os.walk(directory):
            for names in files:
                if verbose == 1:
                    print 'Hashing', names
                # skip rendered images if they are there
                if names[-4:] == ".png" or names[-5:] == ".jpeg":
                    print names
                    continue
                filepath = os.path.join(root,names)
                try:
                    f1 = open(filepath, 'rb')
                except:
                    # You can't open the file for some reason
                    f1.close()
                    continue

                while 1:
                    # Read file in as little chunks
                    buf = f1.read(4096)
                    if not buf: 
                        break
                    SHAhash.update(hashlib.sha1(buf).hexdigest())
                f1.close()

    except:
        import traceback
        # Print the stack traceback
        traceback.print_exc()
        return "-1"

    return SHAhash.hexdigest()
