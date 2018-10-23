#[macro_use]
extern crate cpython;

use cpython::PyResult;

mod bindings;

mod marketplace;

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
    Ok(())
});
