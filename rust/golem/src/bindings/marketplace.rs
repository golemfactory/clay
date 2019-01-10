use cpython::{FromPyObject, ObjectProtocol, PyObject, PyResult, Python};

use marketplace;

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
