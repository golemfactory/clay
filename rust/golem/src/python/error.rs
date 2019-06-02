use std::{convert, error, fmt, io, sync};
use std::net::AddrParseError;

use cpython::{PyErr, PyInt, PyString, Python, ToPyObject};

use crate::bindings::net::PyNetworkServiceError;

#[derive(Debug, Copy, Clone)]
pub enum ErrorKind {
    Io = 0,
    PyExt = 1,
    Other = 2,
}

impl ToPyObject for ErrorKind {
    type ObjectType = PyInt;

    fn to_py_object(&self, py: Python) -> Self::ObjectType {
        py_wrap!(py, *self as u32)
    }
}

#[derive(Debug, Copy, Clone)]
pub enum ErrorSeverity {
    Low = 0,
    Medium = 2,
    High = 4,
    Other = 5,
}

impl ToPyObject for ErrorSeverity {
    type ObjectType = PyInt;

    fn to_py_object(&self, py: Python) -> Self::ObjectType {
        py_wrap!(py, *self as u32)
    }
}

#[derive(Debug)]
pub struct Error {
    pub kind: ErrorKind,
    pub severity: ErrorSeverity,
    pub message: String,
    py_err: Option<PyErr>,
}

impl Error {
    pub fn new<S>(
        kind: ErrorKind,
        severity: ErrorSeverity,
        message: S,
        py_err: Option<PyErr>,
    ) -> Self
    where
        S: Into<String>,
    {
        Error {
            kind,
            severity,
            message: message.into(),
            py_err,
        }
    }

    pub fn already_running() -> Self {
        Error::new(
            ErrorKind::PyExt,
            ErrorSeverity::Low,
            "already running",
            None,
        )
    }

    pub fn not_running() -> Self {
        Error::new(ErrorKind::PyExt, ErrorSeverity::High, "not running", None)
    }
}

unsafe impl Send for Error {}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "{:?} ({:?}): {}", self.kind, self.severity, self.message)
    }
}

impl error::Error for Error {
    fn description(&self) -> &str {
        self.message.as_str()
    }

    fn cause(&self) -> Option<&error::Error> {
        None
    }
}

impl convert::From<io::Error> for Error {
    fn from(e: io::Error) -> Self {
        Error::new(
            ErrorKind::Io,
            ErrorSeverity::Medium,
            format!("{:?}", e),
            None,
        )
    }
}

impl convert::From<sync::mpsc::RecvError> for Error {
    fn from(e: sync::mpsc::RecvError) -> Self {
        Error::new(
            ErrorKind::Other,
            ErrorSeverity::High,
            format!("{:?}", e),
            None,
        )
    }
}

impl convert::From<AddrParseError> for Error {
    fn from(e: AddrParseError) -> Self {
        Error::new(
            ErrorKind::Other,
            ErrorSeverity::Medium,
            format!("{:?}", e),
            None,
        )
    }
}

impl convert::From<network::error::Error> for Error {
    fn from(e: network::error::Error) -> Self {
        Error::new(
            ErrorKind::Io,
            ErrorSeverity::Other,
            format!("{:?}", e),
            None,
        )
    }
}

impl convert::From<PyErr> for Error {
    fn from(e: PyErr) -> Self {
        Error::new(
            ErrorKind::PyExt,
            ErrorSeverity::High,
            format!("{:?}", e),
            Some(e),
        )
    }
}

impl convert::Into<PyErr> for Error {
    fn into(self) -> PyErr {
        match self.py_err {
            Some(e) => e,
            None => {
                let gil = Python::acquire_gil();
                let py = gil.python();

                let msg = <Self as error::Error>::description(&self);
                let py_msg = PyString::new(py, &msg[..]);

                PyErr::new::<PyNetworkServiceError, PyString>(py, py_msg)
            }
        }
    }
}
