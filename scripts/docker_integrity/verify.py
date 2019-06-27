#!/usr/bin/env python
import json
import pathlib
import re
import requests
from requests.status_codes import codes as http_codes
import sys

DOCKERHUB_URI = 'https://registry.hub.docker.com/v2/'
REPOSITORY_ROOT = 'golemfactory'
IMAGES_FILE = pathlib.Path(__file__).parents[2] / 'apps/image_integrity.ini'


class COLORS(object):
    RESET = '\033[0m'
    RED = '\033[1;31m'
    GREEN = '\033[1;32m'


class AuthenticationError(Exception):
    pass


class ConfigurationError(Exception):
    pass


class CommunicationError(Exception):
    pass


def get_images() -> dict:
    images = {}
    with open(IMAGES_FILE) as f:
        for l in f:
            m = re.match(
                r"(?P<repo>[\w._/]+)\s+(?P<tag>[\w.]+)\s+(?P<hash>\w+)?$", l)

            if not m:
                continue

            m_repo = m.group('repo')
            m_tag = m.group('tag')

            repo = images.setdefault(m_repo, {})

            if m_tag in repo and m.group('hash') != repo.get(m_tag):
                raise ConfigurationError(
                    f"{m_repo}:{m_tag} has a conflicting hash: "
                    f"'{m.group('hash')}' vs '{repo.get(m_tag)}' "
                    f"defined in '{IMAGES_FILE}'."
                )
            else:
                repo[m.group('tag')] = m.group('hash')

    return images


def authenticate(repository: str):
    r = requests.get(DOCKERHUB_URI)
    if not r.status_code == http_codes.UNAUTHORIZED:
        raise AuthenticationError(
            f"Unexpected status code: {r.status_code} "
            f"while retrieving: {DOCKERHUB_URI}"
        )
    auth_properties = {
        g[0]: g[1]
        for g in re.findall(
            r"(\w+)=\"(.+?)\"", r.headers.get('Www-Authenticate', '')
        )
    }
    realm = auth_properties.get('realm')
    if not realm:
        raise AuthenticationError(
            f"Could not find expected auth header in: {r.headers}"
        )
    auth_r = requests.get(
        realm,
        params={
            'service': auth_properties.get('service'),
            'scope': f'repository:{repository}:pull',
        }
    )
    if not auth_r.status_code == http_codes.OK:
        raise AuthenticationError(
            f"Could not access: {realm}"
        )
    try:
        token = auth_r.json().get('token')
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.docker.distribution.manifest.v2+json'
        }
    except json.decoder.JSONDecodeError:
        raise AuthenticationError(
            f"Auth token not found in {auth_r.text}, retrieved from {realm}."
        )


def get_manifest(token: dict, repository: str, tag: str):
    r = requests.get(
        DOCKERHUB_URI + f'{repository}/manifests/{tag}',
        headers=token
    )
    try:
        manifest = r.json()
        if not isinstance(manifest, dict):
            raise CommunicationError(
                f"Expected a dictionary, got {type(manifest)}: {manifest} "
                f"for {repository}:{tag}"
            )
    except json.JSONDecodeError as e:
        raise CommunicationError(
            f"Failed to retrieve the correct manifest for {repository}:{tag}, "
            f"got {r.status_code} - {r.text}"
        ) from e

    return manifest


def get_info(repository: str, tag: str):
    r = requests.get(DOCKERHUB_URI + f'repositories/{repository}/tags/{tag}/')
    try:
        info = r.json()
        if not isinstance(info, dict):
            raise CommunicationError(
                f"Expected a dictionary, got {type(info)}: {info} "
                f"for {repository}:{tag}"
            )
    except json.JSONDecodeError as e:
        raise CommunicationError(
            f"Failed to retrieve image info for {repository}:{tag}, "
            f"got {r.status_code} - {r.text}"
        ) from e

    return info


def verify_images() -> (int, int):
    cnt_images = 0
    cnt_failures = 0
    for repository, tags in get_images().items():
        token = authenticate(repository)
        for tag, img_hash in tags.items():
            cnt_images += 1
            manifest = get_manifest(token, repository, tag)
            manifest_hash = manifest.get('config', {}).get('digest', '')[7:]
            if img_hash != manifest_hash:
                last_updated = get_info(repository, tag).get('last_updated')
                print(
                    f'{repository}:{tag}: '
                    f'{COLORS.RED}hash differs '
                    f'(expected:{img_hash}, received:{manifest_hash}).'
                    f'{COLORS.RESET}'
                    f' Last updated: {last_updated}'
                )
                cnt_failures += 1
            else:
                print(
                    f'{repository}:{tag}: {COLORS.GREEN}\u2713{COLORS.RESET}'
                )

    return cnt_images, cnt_failures


def run_verification():

    cnt_images, cnt_failures = verify_images()

    if cnt_failures:
        print(
            f'{COLORS.RED}{cnt_failures} out of {cnt_images} images '
            f'had modified hashes!{COLORS.RESET}'
        )
        sys.exit(1)

    print(
        f'{COLORS.GREEN}All {cnt_images} images successfully verified :)'
        f'{COLORS.RESET}'
    )
    sys.exit(0)


print("Verifying Golem Docker image integrity...")
run_verification()
