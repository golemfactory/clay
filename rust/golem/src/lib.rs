#[macro_use]
extern crate cpython;

use cpython::{FromPyObject, ObjectProtocol, PyObject, PyResult, Python};

mod marketplace;

impl<'source> FromPyObject<'source> for marketplace::Offer {
    fn extract(py: Python, obj: &'source PyObject) -> PyResult<Self> {
        let quality = obj
            .getattr(py, "quality")?
            .extract::<(f64, f64, f64, f64)>(py)?;
        Ok(marketplace::Offer {
            scaled_price: obj.getattr(py, "scaled_price")?.extract::<f64>(py)?,
            reputation: obj.getattr(py, "reputation")?.extract::<f64>(py)?,
            quality: marketplace::Quality {
                s: quality.0,
                t: quality.1,
                f: quality.2,
                r: quality.3,
            },
        })
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
    Ok(())
});
