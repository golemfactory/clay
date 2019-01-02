#[macro_use]
extern crate cpython;
#[cfg(windows)]
extern crate winapi;

use cpython::{exc, PyErr, PyObject, PyResult, Python};

mod bindings;
mod marketplace;
mod os;


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

py_module_initializer!(libgolem, initlibgolem, PyInit_golem, |_py, m| {
    try!(m.add(_py, "__doc__", "Parts of Golem core implemented in Rust"));
    try!(m.add(
        _py,
        "marketplace__order_providers",
        py_fn!(
            _py,
            marketplace__order_providers(offers: Vec<marketplace::Offer>) -> PyResult<Vec<usize>> {
                Ok(marketplace::order_providers(offers))
            }
        )
    ));
    try!(m.add(
        _py,
        "os__windows__empty_working_sets",
        py_fn!(_py, os__windows__empty_working_sets())
    ));
    Ok(())
});
