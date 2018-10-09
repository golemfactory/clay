#[macro_use]
extern crate cpython;

use cpython::{PyList, PyResult, Python};

mod marketplace;

#[allow(non_snake_case)]
fn marketplace__pick_provider(py: Python, pyoffers: PyList) -> PyResult<u32> {
    let mut offers = Vec::with_capacity(pyoffers.len(py));
    for pyoffer in pyoffers.iter(py) {
        offers.push(pyoffer.extract::<f64>(py)?);
    }
    Ok(marketplace::pick_provider(&offers))
}

py_module_initializer!(libgolem, initlibgolem, PyInit_golem, |py, m| {
    try!(m.add(py, "__doc__", "Parts of Golem core implemented in Rust"));
    try!(m.add(
        py,
        "marketplace__pick_provider",
        py_fn!(py, marketplace__pick_provider(offers: PyList))
    ));
    Ok(())
});
