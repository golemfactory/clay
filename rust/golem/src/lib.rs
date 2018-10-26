#[macro_use]
extern crate cpython;

use cpython::{PyResult, Python};

mod marketplace;

#[allow(non_snake_case)]
fn marketplace__order_providers(_py: Python, offers: Vec<f64>) -> PyResult<Vec<usize>> {
    let offers: Vec<marketplace::Offer> = offers
        .iter()
        .map(|price| marketplace::Offer::new(*price))
        .collect();
    Ok(marketplace::order_providers(&offers))
}

py_module_initializer!(libgolem, initlibgolem, PyInit_golem, |py, m| {
    try!(m.add(py, "__doc__", "Parts of Golem core implemented in Rust"));
    try!(m.add(
        py,
        "marketplace__order_providers",
        py_fn!(py, marketplace__order_providers(offers: Vec<f64>))
    ));
    Ok(())
});
