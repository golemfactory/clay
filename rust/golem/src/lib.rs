#![allow(non_upper_case_globals)]
#![allow(unused_variables)]

#[macro_use]
extern crate cpython;
extern crate env_logger;
extern crate futures;
#[macro_use]
extern crate lazy_static;
extern crate log;
#[cfg(windows)]
extern crate winapi;

use cpython::{exc, PyErr, PyObject, PyResult, Python};

#[macro_use]
mod python;

mod logger;
mod marketplace;
mod net;
mod os;

mod bindings;

#[allow(non_snake_case)]
fn os__windows__empty_working_sets(py: Python) -> PyResult<PyObject> {
    match os::windows::empty_working_sets() {
        Err(e) => {
            let py_err = PyErr::new::<exc::OSError, _>(py, format!("{:?}", e));
            Err(py_err)
        }
        Ok(_) => Ok(Python::None(py)),
    }
}

py_module_initializer!(libgolem, initlibgolem, PyInit_golem, |py, m| {
    logger::init();

    m.add(py, "__doc__", "Parts of Golem core implemented in Rust")?;
    m.add(
        py,
        "NetworkService",
        py.get_type::<bindings::net::PyNetworkService>(),
    )?;
    m.add(
        py,
        "NetworkServiceError",
        py.get_type::<bindings::net::PyNetworkServiceError>(),
    )?;
    m.add(
        py,
        "marketplace__order_providers",
        py_fn!(
            py,
            marketplace__order_providers(offers: Vec<marketplace::Offer>) -> PyResult<Vec<usize>> {
                Ok(marketplace::order_providers(offers))
            }
        ),
    )?;
    m.add(
        py,
        "os__windows__empty_working_sets",
        py_fn!(py, os__windows__empty_working_sets()),
    )?;
    Ok(())
});
