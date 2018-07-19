import os
import subprocess
import tempfile

from eth_utils import decode_hex, encode_hex
from pathlib import Path

AGENT_PATH = Path('/home/admin_imapp/golem_repos/graphene-ng/Pal/src/host/Linux-SGX/agent')  # noqa


def generate_wrap_key(wrap_key: Path):
    print("generate_wrap_key")
    res = subprocess.run([
        str(AGENT_PATH / "prepare_input"),
        "gen_key",
        "--wrap-key", str(wrap_key),
    ])
    print(res)


def encrypt_file(wrap_key: Path, file: Path, out_file: Path):
    print("encrypt_file")
    res = subprocess.run([
        str(AGENT_PATH / "prepare_input"),
        "chunk",
        "--wrap-key", str(wrap_key),
        "--input", str(file),
        "--output", str(out_file),
        "--prefix", "/enc_input",
    ])
    print(res)


def decrypt_file(wrap_key: Path, file: Path, out_file: Path):
    print("decrypt_file")
    res = subprocess.run([
        str(AGENT_PATH / "decrypt_output"),
        "--wrap-key", str(wrap_key),
        "--input", str(file),
        "--output", str(out_file),
    ])
    print(res)


def init_agent(agent_pubkey: Path):
    print("init_agent")
    res = subprocess.run([
        str(AGENT_PATH / "agent"),
        "init",
        "-e", str(AGENT_PATH / "agent_enclave.signed.so"),
        "--pubkey-path", str(agent_pubkey),
        "--spid", "002C842565241853FC8690DF78C40834",
        "--quote-type", "u",
    ])
    print(res)


def encrypt_wrap_key(wrap_key: Path, agent_pubkey: str) -> str:
    print("encrypt_wrap_key")
    """
    wrap_key: symmetric key used for input/output encryption
    agent_pubkey: public key of the provider's enclave
    return: hex encoded encrypted wrap key
    """
    fd, agent_pubkey_filepath = tempfile.mkstemp()
    os.write(fd, agent_pubkey.encode())
    os.close(fd)

    fd, agent_encrypted_key_filepath = tempfile.mkstemp()
    os.close(fd)
    res = subprocess.run([
        str(AGENT_PATH / "prepare_input"),
        "export",
        "--no-verification",
        "--wrap-key", str(wrap_key),
        "--agent-public-key", agent_pubkey_filepath,
        "--agent-encrypted-key", agent_encrypted_key_filepath,
    ])
    print(res)

    with open(agent_encrypted_key_filepath, 'rb') as f:
        res = f.read()
    os.remove(agent_pubkey_filepath)
    os.remove(agent_encrypted_key_filepath)
    return encode_hex(res)[2:]


def docker_run(
        docker_image: str,
        wrap_key: str,
        input_path: Path,
        output_path: Path,
        enc_input: Path,
        enc_output: Path):
    print('docker_run')
    wrap_key = decode_hex(wrap_key)
    fd, wrap_key_file = tempfile.mkstemp()
    os.write(fd, wrap_key)
    os.close(fd)
    res = subprocess.run([
        str(AGENT_PATH / "agent"),
        "docker_run",
        "-e", str(AGENT_PATH / "agent_enclave.signed.so"),
        "--docker-image", docker_image,
        "--input-enc-path", str(enc_input),
        "--output-enc-path", str(enc_output),
        "--input-path", str(input_path),
        "--output-path", str(output_path),
        "--wrap-key-path", str(wrap_key_file),
        "--wait", "1000000",
    ])
    print(res)
