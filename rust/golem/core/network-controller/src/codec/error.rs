use bincode::ErrorKind;
use std::{convert, error, fmt, io};

#[derive(Debug, Clone)]
pub struct CodecError {
    message: String,
}

impl CodecError {
    pub fn new(message: &str) -> Self {
        CodecError {
            message: message.to_string(),
        }
    }
}

impl error::Error for CodecError {
    fn description(&self) -> &str {
        &self.message[..]
    }

    fn cause(&self) -> Option<&error::Error> {
        None
    }
}

impl fmt::Display for CodecError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "codec error: {}", &self.message[..])
    }
}

impl convert::From<io::Error> for CodecError {
    fn from(e: io::Error) -> Self {
        CodecError::new(&format!("io error: {}", e))
    }
}

impl convert::From<Box<ErrorKind>> for CodecError {
    fn from(e: Box<ErrorKind>) -> Self {
        CodecError::new(&format!("bincode error: {}", e))
    }
}

impl convert::From<()> for CodecError {
    fn from(_: ()) -> Self {
        CodecError::new("unknown error")
    }
}
