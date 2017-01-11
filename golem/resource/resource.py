import logging
import os
import string
import unicodedata
import zipfile

from golem.core.simplehash import SimpleHash
from golem.resource.dirmanager import split_path


logger = logging.getLogger(__name__)


class TaskResourceHeader(object):
    def __init__(self, dir_name):
        self.sub_dir_headers = []
        self.files_data = []
        self.dir_name = dir_name

    def __eq__(self, other):
        if self.dir_name != other.dir_name:
            return False
        if self.files_data != other.files_data:
            return False
        if len(self.sub_dir_headers) != len(other.sub_dir_headers):
            return False
        sub1 = sorted(self.sub_dir_headers, lambda x: x.dir_name)
        sub2 = sorted(other.sub_dir_headers, lambda x: x.dir_name)
        for i in range(len(self.sub_dir_headers)):
            if not (sub1[i] == sub2[i]):
                return False
        return True

    @classmethod
    def build(cls, relative_root, absolute_root):
        return cls.__build(relative_root, absolute_root)

    @classmethod
    def build_from_chosen(cls, dir_name, absolute_root, chosen_files=None):
        cur_th = TaskResourceHeader(dir_name)

        abs_dirs = split_path(absolute_root)

        for f in chosen_files:

            dir_, file_name = os.path.split(f)
            dirs = split_path(dir_)[len(abs_dirs):]

            last_header = cur_th

            for d in dirs:

                child_sub_dir_header = TaskResourceHeader(d)
                if last_header.__has_sub_header(d):
                    last_header = last_header.__get_sub_header(d)
                else:
                    last_header.sub_dir_headers.append(child_sub_dir_header)
                    last_header = child_sub_dir_header

            hsh = SimpleHash.hash_file_base64(f)
            last_header.files_data.append((file_name, hsh))

        return cur_th

    @classmethod
    def __build(cls, dir_name, absolute_root, chosen_files=None):
        cur_th = TaskResourceHeader(dir_name)

        dirs = [name for name in os.listdir(absolute_root) if os.path.isdir(os.path.join(absolute_root, name))]
        files = [name for name in os.listdir(absolute_root) if os.path.isfile(os.path.join(absolute_root, name))]

        files_data = []
        for f in files:
            if chosen_files and os.path.join(absolute_root, f) not in chosen_files:
                continue
            hsh = SimpleHash.hash_file_base64(os.path.join(absolute_root, f))

            files_data.append((f, hsh))

        # print "{}, {}, {}".format(relative_root, absolute_root, files_data)

        cur_th.files_data = files_data

        sub_dir_headers = []
        for d in dirs:
            child_sub_dir_header = cls.__build(d, os.path.join(absolute_root, d), chosen_files)
            sub_dir_headers.append(child_sub_dir_header)

        cur_th.sub_dir_headers = sub_dir_headers
        # print "{} {} {}\n".format(absolute_root, len(sub_dir_headers), len(files_data))

        return cur_th

    @classmethod
    def build_header_delta_from_chosen(cls, header, absolute_root, chosen_files=[]):
        if not isinstance(header, TaskResourceHeader):
            raise TypeError("Incorrect header type: {}. Should be TaskResourceHeader".format(type(header)))
        cur_th = TaskResourceHeader(header.dir_name)

        abs_dirs = split_path(absolute_root)

        for file_ in chosen_files:

            dir_, file_name = os.path.split(file_)
            dirs = split_path(dir_)[len(abs_dirs):]

            last_header = cur_th
            last_ref_header = header

            last_header, last_ref_header, ref_header_found = cls.__resolve_dirs(dirs, last_header, last_ref_header)

            hsh = SimpleHash.hash_file_base64(file_)
            if ref_header_found:
                if last_ref_header.__has_file(file_name):
                    if hsh == last_ref_header.__get_file_hash(file_name):
                        continue
            last_header.files_data.append((file_name, hsh))

        return cur_th

    @classmethod
    def build_parts_header_delta_from_chosen(cls, header, absolute_root, res_parts):
        if not isinstance(header, TaskResourceHeader):
            raise TypeError("Incorrect header type: {}. Should be TaskResourceHeader".format(type(header)))
        cur_th = TaskResourceHeader(header.dir_name)
        abs_dirs = split_path(absolute_root)
        delta_parts = []

        for file_, parts in res_parts.iteritems():
            dir_, file_name = os.path.split(file_)
            dirs = split_path(dir_)[len(abs_dirs):]

            last_header = cur_th
            last_ref_header = header

            last_header, last_ref_header, ref_header_found = cls.__resolve_dirs(dirs, last_header, last_ref_header)

            hsh = SimpleHash.hash_file_base64(file_)
            if ref_header_found:
                if last_ref_header.__has_file(file_name):
                    if hsh == last_ref_header.__get_file_hash(file_name):
                        continue
            last_header.files_data.append((file_name, hsh, parts))
            delta_parts += parts

        return cur_th, delta_parts

    # Add only the fields that are not in header (or which hashes are different)
    @classmethod
    def build_header_delta_from_header(cls, header, absolute_root, chosen_files):
        if not isinstance(header, TaskResourceHeader):
            raise TypeError("Incorrect header type: {}. Should be TaskResourceHeader".format(type(header)))

        cur_tr = TaskResourceHeader(header.dir_name)

        dirs = [name for name in os.listdir(absolute_root) if os.path.isdir(os.path.join(absolute_root, name))]
        files = [name for name in os.listdir(absolute_root) if os.path.isfile(os.path.join(absolute_root, name))]

        for d in dirs:
            if header.__has_sub_header(d):
                cur_tr.sub_dir_headers.append(
                    cls.build_header_delta_from_header(header.__get_sub_header(d), os.path.join(absolute_root, d),
                                                       chosen_files))
            else:
                cur_tr.sub_dir_headers.append(cls.__build(d, os.path.join(absolute_root, d), chosen_files))

        for f in files:
            if chosen_files and os.path.join(absolute_root, f) not in chosen_files:
                continue

            file_hash = 0
            if header.__has_file(f):
                file_hash = SimpleHash.hash_file_base64(os.path.join(absolute_root, f))

                if file_hash == header.__get_file_hash(f):
                    continue

            if not file_hash:
                file_hash = SimpleHash.hash_file_base64(os.path.join(absolute_root, f))

            cur_tr.files_data.append((f, file_hash))

        return cur_tr

    @classmethod
    def __resolve_dirs(cls, dirs, last_header, last_ref_header):
        ref_header_found = True
        for d in dirs:

            child_sub_dir_header = TaskResourceHeader(d)

            if last_header.__has_sub_header(d):
                last_header = last_header.__get_sub_header(d)
            else:
                last_header.sub_dir_headers.append(child_sub_dir_header)
                last_header = child_sub_dir_header

            if ref_header_found:
                if last_ref_header.__has_sub_header(d):
                    last_ref_header = last_ref_header.__get_sub_header(d)
                else:
                    ref_header_found = False
        return last_header, last_ref_header, ref_header_found

    def to_string(self):
        out = u"\nROOT '{}' \n".format(self.dir_name)

        if len(self.sub_dir_headers) > 0:
            out += u"DIRS \n"
            for d in self.sub_dir_headers:
                out += u"    {}\n".format(d.dir_name)

        if len(self.files_data) > 0:
            out += u"FILES \n"
            for f in self.files_data:
                if len(f) > 2:
                    out += u"    {} {} {}".format(f[0], f[1], f[2])
                else:
                    out += u"    {} {}".format(f[0], f[1])

        for d in self.sub_dir_headers:
            out += d.to_string()

        return out

    def __str__(self):
        return self.to_string()

    def hash(self):
        return SimpleHash.hash_base64(self.to_string().encode('utf-8'))

    def __has_sub_header(self, dir_name):
        return dir_name in [sh.dir_name for sh in self.sub_dir_headers]

    def __has_file(self, file_):
        return file_ in [f[0] for f in self.files_data]

    def __get_sub_header(self, dir_name):
        idx = [sh.dir_name for sh in self.sub_dir_headers].index(dir_name)
        return self.sub_dir_headers[idx]

    def __get_file_hash(self, file_):
        idx = [f[0] for f in self.files_data].index(file_)
        return self.files_data[idx][1]


class TaskResource(object):
    @classmethod
    def __build(cls, dir_name, absolute_root):
        cur_th = TaskResource(dir_name)

        dirs = [name for name in os.listdir(absolute_root) if os.path.isdir(os.path.join(absolute_root, name))]
        files = [name for name in os.listdir(absolute_root) if os.path.isfile(os.path.join(absolute_root, name))]

        files_data = []
        for f in files:
            file_data = cls.read_file(os.path.join(absolute_root, f))
            hsh = SimpleHash.hash_base64(file_data)
            files_data.append((f, hsh, file_data))

        # print "{}, {}, {}".format(relative_root, absolute_root, files_data)

        cur_th.files_data = files_data

        sub_dir_resources = []
        for d in dirs:
            child_sub_dir_header = cls.__build(d, os.path.join(absolute_root, d))
            sub_dir_resources.append(child_sub_dir_header)

        cur_th.sub_dir_resources = sub_dir_resources
        # print "{} {} {}\n".format(absolute_root, len(sub_dir_headers), len(files_data))

        return cur_th

    @classmethod
    def read_file(cls, file_name):
        try:
            f = open(file_name, "rb")
            data = f.read()
        except Exception as ex:
            logger.error(str(ex))
            return None

        return data

    @classmethod
    def write_file(cls, file_name, data):
        try:
            f = open(file_name, "wb")
            f.write(data)
        except Exception as ex:
            logger.error(str(ex))

    @classmethod
    def validate_header(cls, header, absolute_root):
        if not isinstance(header, TaskResourceHeader):
            raise TypeError("Incorrect header type: {}. Should be TaskResourceHeader".format(type(header)))

        for f in header.files_data:
            fname = os.path.join(absolute_root, f[0])

            if not os.path.exists(fname):
                return False, "File {} does not exist".format(fname)

            if not os.path.isfile(fname):
                return False, "Entry {} is not a file".format(fname)

        for dh in header.sub_dir_headers:
            validated, msg = cls.validate_header(dh, os.path.join(absolute_root, dh.dir_name))

            if not validated:
                return validated, msg

        return True, None

    @classmethod
    def build_from_header(cls, header, absolute_root):
        if not isinstance(header, TaskResourceHeader):
            raise TypeError("Incorrect header type: {}. Should be TaskResourceHeader".format(type(header)))

        cur_tr = TaskResource(header.dir_name)

        files_data = []
        for f in header.files_data:
            fname = os.path.join(absolute_root, f[0])
            fdata = cls.read_file(fname)

            if fdata is None:
                return None

            files_data.append((f[0], f[1], fdata))

        cur_tr.files_data = files_data

        sub_dir_resources = []
        for sdh in header.sub_dir_headers:
            sub_dir_res = cls.build_from_header(sdh, os.path.join(absolute_root, sdh.dir_name))

            if sub_dir_res is None:
                return None

            sub_dir_resources.append(sub_dir_res)

        cur_tr.sub_dir_resources = sub_dir_resources

        return cur_tr

    # Add only the fields that are not in header (or which hashes are different)
    @classmethod
    def build_delta_from_header(cls, header, absolute_root):
        if not isinstance(header, TaskResourceHeader):
            raise TypeError("Incorrect header type: {}. Should be TaskResourceHeader".format(type(header)))

        cur_tr = TaskResource(header.dir_name)

        dirs = [name for name in os.listdir(absolute_root) if os.path.isdir(os.path.join(absolute_root, name))]
        files = [name for name in os.listdir(absolute_root) if os.path.isfile(os.path.join(absolute_root, name))]

        for d in dirs:
            if d in [sdh.dir_name for sdh in header.sub_dir_headers]:
                idx = [sdh.dir_name for sdh in header.sub_dir_headers].index(d)
                cur_tr.sub_dir_resources.append(
                    cls.build_delta_from_header(header.sub_dir_headers[idx], os.path.join(absolute_root, d)))
            else:
                cur_tr.sub_dir_resources.append(cls.__build(d, os.path.join(absolute_root, d)))

        for f in files:
            if f in [file_[0] for file_ in header.files_data]:
                idx = [file_[0] for file_ in header.files_data].index(f)
                if SimpleHash.hash_file_base64(os.path.join(absolute_root, f)) == header.files_data[idx][1]:
                    continue

            fdata = cls.read_file(os.path.join(absolute_root, f))

            if fdata is None:
                return None

            cur_tr.files_data.append((f, SimpleHash.hash_base64(fdata), fdata))

        return cur_tr

    def extract(self, to_path):
        for dir_ in self.sub_dir_resources:
            if not os.path.exists(os.path.join(to_path, dir_.dir_name)):
                os.makedirs(os.path.join(to_path, dir_.dir_name))

            dir_.extract(os.path.join(to_path, dir_.dir_name))

        for f in self.files_data:
            if not os.path.exists(os.path.join(to_path, f[0])) or SimpleHash.hash_file_base64(
                    os.path.join(to_path, f[0])) != f[1]:
                self.write_file(os.path.join(to_path, f[0]), f[2])

    def __init__(self, dir_name):
        self.files_data = []
        self.sub_dir_resources = []
        self.dir_name = dir_name

    def to_string(self):
        out = "\nROOT '{}' \n".format(self.dir_name)

        if len(self.sub_dir_resources) > 0:
            out += "DIRS \n"
            for d in self.sub_dir_resources:
                out += "    {}\n".format(d.dir_name)

        if len(self.files_data) > 0:
            out += "FILES \n"
            for f in self.files_data:
                out += "    {:10} {} {}".format(len(f[2]), f[0], f[1])

        for d in self.sub_dir_resources:
            out += d.to_string()

        return out

    def __str__(self):
        return self.to_string()


valid_filename_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)


def remove_disallowed_filename_chars(filename):
    cleaned_filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore')
    return ''.join(c for c in cleaned_filename if c in valid_filename_chars)


def compress_dir(root_path, header, output_dir):
    output_file = remove_disallowed_filename_chars(header.hash().strip().decode('unicode-escape') + ".zip")

    output_file = os.path.join(output_dir, output_file)

    zipf = zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True)

    cur_working_dir = os.getcwd()
    os.chdir(root_path)
    logger.debug("Working directory {}".format(os.getcwd()))

    try:
        compress_dir_impl("", header, zipf)

        zipf.close()
    finally:
        os.chdir(cur_working_dir)
        logger.debug("Return to prev working directory {}".format(os.getcwd()))

    return output_file


def decompress_dir(root_path, zip_file):
    zipf = zipfile.ZipFile(zip_file, 'r', allowZip64=True)

    zipf.extractall(root_path)


def compress_dir_impl(root_path, header, zipf):
    for sdh in header.sub_dir_headers:
        compress_dir_impl(os.path.join(root_path, sdh.dir_name), sdh, zipf)

    for fdata in header.files_data:
        zipf.write(os.path.join(root_path, fdata[0]))


def prepare_delta_zip(root_dir, header, output_dir, chosen_files=None):
    # delta_header = TaskResourceHeader.build_header_delta_from_header(header, root_dir, chosen_files)
    delta_header = TaskResourceHeader.build_header_delta_from_chosen(header, root_dir, chosen_files)
    return compress_dir(root_dir, delta_header, output_dir)
