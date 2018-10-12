#[macro_use]
extern crate cpython;

use cpython::{PyList, PyResult, Python};

mod marketplace;

#[allow(non_snake_case)]
fn marketplace__order_providers(py: Python, pyoffers: PyList) -> PyResult<Vec<usize>> {
    let mut offers = Vec::with_capacity(pyoffers.len(py));
    for pyoffer in pyoffers.iter(py) {
        offers.push(pyoffer.extract::<f64>(py)?);
    }
    Ok(marketplace::order_providers(&offers))
}

py_module_initializer!(libgolem, initlibgolem, PyInit_golem, |py, m| {
    try!(m.add(py, "__doc__", "Parts of Golem core implemented in Rust"));
    try!(m.add(
        py,
        "marketplace__order_providers",
        py_fn!(py, marketplace__order_providers(offers: PyList))
    ));
    Ok(())
});
