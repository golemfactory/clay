#![allow(non_upper_case_globals)]
#![allow(unused_variables)]
use std::time::Duration;

use cpython::*;
use parking_lot::{Mutex, MutexGuard};

use crate::net::event::event_into;
use crate::net::service::NetworkService;

lazy_static! {
    static ref NETWORK_SERVICE: Mutex<NetworkService> = Mutex::new(NetworkService::new());
}

#[inline]
fn net() -> MutexGuard<'static, NetworkService> {
    NETWORK_SERVICE.lock()
}

py_exception!(libgolem_core, PyNetworkServiceError);
py_class!(pub class PyNetworkService |py| {

    def __new__(_cls) -> PyResult<PyNetworkService> {
        PyNetworkService::create_instance(py)
    }

    def start(
        &self,
        priv_key: PyBytes,
        host: PyString,
        port: PyInt
    ) -> PyResult<bool> {
        match net().start(py, priv_key, host, port) {
            Ok(_) => Ok(true),
            Err(e) => Err(e.into())
        }
    }

    def stop(&self) -> PyResult<bool> {
        match net().stop() {
            Ok(_) => Ok(true),
            Err(e) => Err(e.into())
        }
    }

    def running(&self) -> PyResult<bool> {
        Ok(net().running())
    }

    def connect(
        &self,
        host: PyString,
        port: PyLong
    ) -> PyResult<bool> {
        match net().connect(py, host, port) {
            Ok(_) => Ok(true),
            Err(e) => Err(e.into()),
        }
    }

    def connect_to_peer(
        &self,
        peer_id: PyString
    ) -> PyResult<bool> {
        match net().connect_to_peer(py, peer_id) {
            Ok(_) => Ok(true),
            Err(e) => Err(e.into()),
        }
    }

    def disconnect(
        &self,
        peer_id: PyString
    ) -> PyResult<bool> {
        match net().disconnect(py, peer_id) {
            Ok(_) => Ok(true),
            Err(e) => Err(e.into()),
        }
    }

    def send(
        &self,
        peer_id: PyString,
        message: PyBytes
    ) -> PyResult<bool> {
        match net().send(py, peer_id, message) {
            Ok(_) => Ok(true),
            Err(e) => Err(e.into()),
        }
    }

    def poll(&self, timeout: PyFloat) -> PyResult<Option<PyTuple>> {
        let rx = {
            let net = net();
            if !net.running() {
                return Ok(None);
            }
            net.event_rx.clone()
        };

        match rx {
            None => Ok(None),
            Some(ref rx) => {
                let timeout: f64 = timeout.into_object().extract(py)?;
                let timeout: u64 = (timeout * 1000.0) as u64;

                if timeout > 0 {
                    let duration = Duration::from_millis(timeout);
                    // give control back to Python's VM for the time
                    match py.allow_threads(|| rx.recv_timeout(duration)) {
                        Ok(ev) => Ok(Some(event_into(py, ev))),
                        Err(e) => Ok(None),
                    }
                } else {
                    match py.allow_threads(|| rx.recv()) {
                        Ok(ev) => Ok(Some(event_into(py, ev))),
                        Err(e) => Ok(None),
                    }
                }
            }
        }
    }
});
