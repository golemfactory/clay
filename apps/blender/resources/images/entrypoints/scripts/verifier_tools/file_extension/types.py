import abc
import typing


class FileType(abc.ABC):
    @property
    @abc.abstractmethod
    def extensions(self) -> typing.AbstractSet[str]:
        """
        List of possible extensions (aliases) for the represented file type.
        :return: a set of strings, each prefixed with a dot.
        """
        pass

    @property
    @abc.abstractmethod
    def output_extension(self) -> str:
        """
        Returns the file extension expected to be used by Blender for its
        output files of the represented file type.
        :return: a file extension string, prefixed with a dot.
        """
        pass


class Bmp(FileType):
    @property
    def extensions(self) -> typing.AbstractSet[str]:
        return frozenset([
            '.bmp',
            '.dib'
        ])

    @property
    def output_extension(self) -> str:
        return '.bmp'


class Jpeg(FileType):
    @property
    def extensions(self) -> typing.AbstractSet[str]:
        return frozenset([
            '.jpg',
            '.jpeg',
            '.jpe',
            '.jif',
            '.jfif',
            '.jfi'
        ])

    @property
    def output_extension(self) -> str:
        return '.jpg'


class Tga(FileType):
    @property
    def extensions(self) -> typing.AbstractSet[str]:
        return frozenset([
            '.tga',
            '.icb',
            '.vda',
            '.vst'
        ])

    @property
    def output_extension(self) -> str:
        return '.tga'
