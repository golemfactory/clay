use crate::python::error::Error;
use cpython::*;
use std::net::{IpAddr, SocketAddr};

/// Converts a native value to a Python type
#[macro_export]
macro_rules! py_wrap {
    ($py:expr, $input:expr) => {{
        $input.to_py_object($py)
    }};
    ($py:expr, $input:expr, $to:ty) => {{
        let result: $to = $input.to_py_object($py);
        result
    }};
}

/// Converts a Python value to a native type
#[macro_export]
macro_rules! py_extract {
    ($input:expr) => {{
        use cpython::Python;

        let gil = Python::acquire_gil();
        let py = gil.python();

        py_extract!(py, $input)
    }};
    ($py:expr, $input:expr) => {{
        use cpython::PythonObject;

        $input.into_object().extract($py)
    }};
    ($py:expr, $input:expr, $to:ty) => {{
        use cpython::{PyErr, PythonObject};

        let result: Result<$to, PyErr> = $input.into_object().extract($py);
        result
    }};
}

/// Converts (PyString, PyLong) tuple to a SocketAddr
pub fn to_socket_address(
    py: Python,
    py_host: PyString,
    py_port: PyLong,
) -> Result<SocketAddr, Error> {
    let host: String = py_extract!(py, py_host)?;
    let port: u16 = py_extract!(py, py_port)?;
    let ip: IpAddr = host.parse()?;

    Ok(SocketAddr::new(ip, port))
}

#[cfg(test)]
mod tests {
    use cpython::{Python, ToPyObject};

    #[test]
    fn extract() {
        let gil = Python::acquire_gil();
        let py = gil.python();
        let value: u16 = py_extract!(5_i32.to_py_object(py)).unwrap();

        assert_eq!(5_u16, value);
    }
}
