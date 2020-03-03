import abc
import datetime
from pathlib import Path
import typing
import xml.etree.ElementTree as xml

from dataclasses import dataclass
import dateutil.parser as date_parser
import requests

from golem.apps import save_app_to_json_file, AppDefinition

S3_BUCKET_URL = 'https://golem-app-definitions.s3.eu-central-1.amazonaws.com/'


class FromXml(abc.ABC):
    """ Base class for objects which can be parsed from XML. This is used to
        provide basic support for handling XML objects with namespaces. """
    def __init__(self, ns_map: typing.Dict[str, str]):
        self._namespace_map = ns_map

    def _get_element(
            self,
            element: xml.Element,
            name: str):
        key, ns_name = list(self._namespace_map.items())[0]
        return element.find(f'{key}:{name}', self._namespace_map)

    def _get_elements(
        self,
        element: xml.Element,
        name: str
    ) -> typing.List[xml.Element]:
        key, ns_name = list(self._namespace_map.items())[0]
        return element.findall(f'{key}:{name}', self._namespace_map)


@dataclass
class Contents(FromXml):
    """ Represents a single `Contents` entry in a bucket listing. Such an entry
        corresponds to an object stored within that bucket. """
    etag: str
    key: str
    last_modified: datetime.datetime
    size: int   # size in bytes

    def __init__(self, root: xml.Element, ns_map: typing.Dict[str, str]):
        super().__init__(ns_map)
        self.key = self._get_element(root, 'Key').text
        self.etag = self._get_element(root, 'ETag').text
        self.size = int(self._get_element(root, 'Size').text)
        self.last_modified = date_parser.isoparse(
            self._get_element(root, 'LastModified').text)


@dataclass
class ListBucketResult(FromXml):
    """ Contains metadata about objects stored in an S3 bucket. """
    contents: typing.List[Contents]

    def __init__(self, root: xml.Element):
        namespace_map = {'ns': _get_namespace(root)}
        super().__init__(namespace_map)

        self.contents = [Contents(e, self._namespace_map)
            for e in self._get_elements(root, 'Contents')]


def _get_namespace(element: xml.Element):
    """ Hacky way of extracting the namespace from an XML element.
        This assumes the document uses Clark's notation for tags
        (i.e. {uri}local_part or local_part for empty namespace). """
    tag = element.tag
    return tag[tag.find("{")+1:tag.rfind("}")]


def get_bucket_listing() -> ListBucketResult:
    response = requests.get(S3_BUCKET_URL)
    root: xml.Element = xml.fromstring(response.content)
    return ListBucketResult(root)


def download_definition(
        key: str,
        destination: Path) -> AppDefinition:
    json = requests.get(f'{S3_BUCKET_URL}{key}').text
    definition = AppDefinition.from_json(json)
    save_app_to_json_file(definition, destination)
    return definition


def download_definitions(app_dir: Path) -> typing.List[AppDefinition]:
    """ Download app definitions from Golem Factory CDN. Only downloads
        definitions which are not already present locally.
        :param: app_dir: path to directory containing local app definitions.
        :return: list of newly downloaded app definitions. """
    new_definitions = []

    for metadata in get_bucket_listing().contents:
        definition_path = app_dir / metadata.key
        if not (definition_path).exists():
            new_definitions.append(
                download_definition(metadata.key, definition_path))

    return new_definitions

