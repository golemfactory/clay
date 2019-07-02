import os


def generate_rpc_certificate(data_dir: str):
    from golem.rpc.cert import CertificateManager
    from golem.rpc.common import CROSSBAR_DIR

    cert_dir = os.path.join(data_dir, CROSSBAR_DIR)
    os.makedirs(cert_dir, exist_ok=True)

    cert_manager = CertificateManager(cert_dir)
    cert_manager.generate_if_needed()


WORKER_PROCESS_MODULE = 'crossbar.worker.main'
