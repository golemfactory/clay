import os
import subprocess
import tempfile

from typing import Tuple

from eth_utils import decode_hex, encode_hex
from pathlib import Path

AGENT_PATH = Path('/home/admin_imapp/golem_repos/graphene-ng/Pal/src/host/Linux-SGX/agent')  # noqa
SPID = "002C842565241853FC8690DF78C40834"
IAS_CLIENT_CERT = "/home/admin_imapp/tls/client.crt"
IAS_CLIENT_KEY = "/home/admin_imapp/tls/client.key"


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


def init_agent(agent_pubkey: Path, quote: Path):
    print("init_agent")
    res = subprocess.run([
        str(AGENT_PATH / "agent"),
        "init",
        "-e", str(AGENT_PATH / "agent_enclave.signed.so"),
        "--pubkey-path", str(agent_pubkey),
        "--spid", SPID,
        "--quote-type", "u",
        "--quote-path", str(quote),
    ])
    print(res)


def agent_attest(quote: Path) -> Tuple[bytes, bytes, bytes]:
    print("agent_attest")
    fd, report_path = tempfile.mkstemp()
    os.close(fd)
    fd, sig_path = tempfile.mkstemp()
    os.close(fd)
    fd, crt_path = tempfile.mkstemp()
    os.close(fd)
    res = subprocess.run([
        str(AGENT_PATH / "agent"),
        "verify",
        "-e", str(AGENT_PATH / "agent_enclave.signed.so"),
        "--quote-path", str(quote),
        "--ias-report-path", report_path,
        "--ias-sig-path", sig_path,
        "--ias-crt-path", crt_path,
        "--ias-client-cert", IAS_CLIENT_CERT,
        "--ias-client-key", IAS_CLIENT_KEY,
    ])
    print(res)
    with open(report_path, "rb") as f:
        report = f.read()
    with open(sig_path, "rb") as f:
        sig = f.read()
    with open(crt_path, "rb") as f:
        crt = f.read()

    os.remove(report_path)
    os.remove(sig_path)
    os.remove(crt_path)

    return (report, sig, crt)


def encrypt_wrap_key(
        wrap_key: Path,
        agent_pubkey: str,
        quote: Path,
        report: Path,
        report_sig: Path) -> bytes:
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
        "--wrap-key", str(wrap_key),
        "--agent-public-key", agent_pubkey_filepath,
        "--agent-encrypted-key", agent_encrypted_key_filepath,
        # "--no-verification",
        "--agent-quote", str(quote),
        "--agent-ias-report", str(report),
        "--agent-ias-sig", str(report_sig),
    ])
    print(res)

    with open(agent_encrypted_key_filepath, 'rb') as f:
        res = f.read()
    os.remove(agent_pubkey_filepath)
    os.remove(agent_encrypted_key_filepath)
    return res


def docker_run(
        docker_image: str,
        wrap_key: bytes,
        input_path: Path,
        output_path: Path,
        enc_input: Path,
        enc_output: Path):
    print('docker_run')
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
