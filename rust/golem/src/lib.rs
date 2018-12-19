#[macro_use]
extern crate cpython;

#[cfg(windows)]
extern crate winapi;

use cpython::{exc, PyErr, PyObject, PyResult, Python};

mod marketplace;
mod os;

#[allow(non_snake_case)]
fn marketplace__order_providers(_py: Python, offers: Vec<f64>) -> PyResult<Vec<usize>> {
    let offers: Vec<marketplace::Offer> = offers
        .iter()
        .map(|price| marketplace::Offer::new(*price))
        .collect();
    Ok(marketplace::order_providers(&offers))
}

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
    try!(m.add(py, "__doc__", "Parts of Golem core implemented in Rust"));
    try!(m.add(
        py,
        "marketplace__order_providers",
        py_fn!(py, marketplace__order_providers(offers: Vec<f64>))
    ));
    try!(m.add(
        py,
        "os__windows__empty_working_sets",
        py_fn!(py, os__windows__empty_working_sets())
    ));
    Ok(())
});
