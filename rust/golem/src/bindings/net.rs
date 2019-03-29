#![allow(non_upper_case_globals)]
#![allow(unused_variables)]

use cpython::*;
use std::time::Duration;

use crate::net::event::event_into;
use crate::net::service::NetworkService;

static mut NETWORK_SERVICE: NetworkService = NetworkService {
    controller: None,
    event_rx: None,
};

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
        unsafe {
            match NETWORK_SERVICE.start(py, priv_key, host, port) {
                Ok(_) => Ok(true),
                Err(e) => Err(e.into())
            }
        }
    }

    def stop(&self) -> PyResult<bool> {
        unsafe {
            match NETWORK_SERVICE.stop() {
                Ok(_) => Ok(true),
                Err(e) => Err(e.into())
            }
        }
    }

    def running(&self) -> PyResult<bool> {
        unsafe {
            Ok(NETWORK_SERVICE.running())
        }
    }

    def connect(
        &self,
        host: PyString,
        port: PyLong
    ) -> PyResult<bool> {
        unsafe {
            match NETWORK_SERVICE.connect(py, host, port) {
                Ok(_) => Ok(true),
                Err(e) => Err(e.into()),
            }
        }
    }

    def connect_to_peer(
        &self,
        peer_id: PyString
    ) -> PyResult<bool> {
        unsafe {
            match NETWORK_SERVICE.connect_to_peer(py, peer_id) {
                Ok(_) => Ok(true),
                Err(e) => Err(e.into()),
            }
        }
    }

    def disconnect(
        &self,
        peer_id: PyString
    ) -> PyResult<bool> {
        unsafe {
            match NETWORK_SERVICE.disconnect(py, peer_id) {
                Ok(_) => Ok(true),
                Err(e) => Err(e.into()),
            }
        }
    }

    def send(
        &self,
        peer_id: PyString,
        message: PyBytes
    ) -> PyResult<bool> {
        unsafe {
            match NETWORK_SERVICE.send(py, peer_id, message) {
                Ok(_) => Ok(true),
                Err(e) => Err(e.into()),
            }
        }
    }

    def poll(&self, timeout: PyLong) -> PyResult<Option<PyTuple>> {
        unsafe {
            if !NETWORK_SERVICE.running() {
                return Ok(None);
            }

            match NETWORK_SERVICE.event_rx {
                None => Ok(None),
                Some(ref event_rx) => {
                    let rx = event_rx.clone();
                    let timeout: i64 = timeout.into_object().extract(py)?;

                    if timeout > 0 {
                        let duration = Duration::from_millis((timeout * 1000) as u64);
                        // give control back to Python's VM for the time
                        match py.allow_threads(|| rx.recv_timeout(duration)) {
                            Ok(ev) => Ok(Some(event_into(py, ev))),
                            Err(e) => Ok(None),
                        }
                    } else {
                        // in-place poll
                        match rx.recv() {
                            Ok(ev) => Ok(Some(event_into(py, ev))),
                            Err(e) => Ok(None),
                        }
                    }
                }
            }
        }
    }
});
