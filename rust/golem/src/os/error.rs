use std::error::Error;
use std::fmt;

#[derive(Debug)]
pub struct OSError {
    message: String
}

impl OSError {
    pub fn new(message: &str) -> Self {
        OSError { message: message.to_string() }
    }
}

impl Error for OSError {}

impl fmt::Display for OSError {
    fn fmt(&self, f: &mut fmt::Formatter) -> Result<(), fmt::Error> {
        f.write_str(self.message.as_str())
    }
}
