from . import types

FILE_TYPES = [
    types.Bmp(),
    types.Jpeg(),
    types.Tga()
]


def get_expected_extension(extension: str) -> str:
    """
    Based on the provided file extension string, returns the expected alias
    extension that Blender will use for its output. This can be used to avoid
    output file names mismatch (e.g. .jpg vs .jpeg extensions). The check is
    based on a predefined list of file types.
    :param extension: file extension string (with leading dot) to check
    against.
    :return: expected output file extension (lowercase, with leading dot).
    Returns the provided file extension if no alias was found.
    """
    lower_extension = extension.lower()

    for file_type in FILE_TYPES:
        if lower_extension in file_type.extensions:
            return file_type.output_extension

    return lower_extension
