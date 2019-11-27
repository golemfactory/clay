import logging
import shutil
import ssl
from ipaddress import IPv4Address
from pathlib import Path
from typing import Optional

import golem_task_api as api

from golem.crypto import (
    generate_rsa_private_key,
    generate_x509_certificate,
    save_rsa_private_key,
    save_x509_certificate,
)

logger = logging.getLogger(__name__)


class SSLContextConfig:
    key_and_cert_directory: Optional[Path] = None


def create_golem_ssl_context(
        shared_directory: Path
) -> Optional[ssl.SSLContext]:
    if not SSLContextConfig.key_and_cert_directory:
        raise RuntimeError("Golem Task API SSL context was not set up")
    return api.ssl.create_client_ssl_context(
        SSLContextConfig.key_and_cert_directory,
        shared_directory)


def create_golem_ssl_context_files(directory: Path):
    SSLContextConfig.key_and_cert_directory = directory

    create_ssl_context_files(
        directory,
        key_file_name=api.ssl.CLIENT_KEY_FILE_NAME,
        cert_file_name=api.ssl.CLIENT_CERT_FILE_NAME,
        label="Golem Task API",
    )


def create_app_ssl_context_files(
        shared_directory: Path
) -> None:
    if not SSLContextConfig.key_and_cert_directory:
        raise RuntimeError("Golem Task API SSL context was not set up")
    create_ssl_context_files(
        shared_directory,
        key_file_name=api.ssl.SERVER_KEY_FILE_NAME,
        cert_file_name=api.ssl.SERVER_CERT_FILE_NAME,
        label="App",
    )
    shutil.copy(
        SSLContextConfig.key_and_cert_directory / api.ssl.CLIENT_CERT_FILE_NAME,
        shared_directory
    )


def create_ssl_context_files(
        directory: Path,
        key_file_name: str,
        cert_file_name: str,
        label: str
) -> None:
    logger.debug('Looking for "%s" SSL context files at %s', label, directory)

    key_file = directory / key_file_name
    cert_file = directory / cert_file_name
    if key_file.exists() and cert_file.exists():
        return

    logger.info('Setting up "%s" SSL context files at %s', label, directory)

    try:
        key = generate_rsa_private_key()
        cert = generate_x509_certificate(
            key,
            names=['localhost'],
            ip_addresses=[IPv4Address('127.0.0.1')])

        directory.mkdir(parents=True, exist_ok=True)
        save_rsa_private_key(key_file, key)
        save_x509_certificate(cert_file, cert)
    except Exception:  # pylint: disable=broad-except
        logger.exception('Unable to create Task API SSL context filex')
        raise

    logger.debug(
        'Completed "%s" SSL context file setup at %s', label, directory)
