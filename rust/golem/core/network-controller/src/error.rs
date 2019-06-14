#![allow(deprecated)]
use error_chain::*;

error_chain! {
    foreign_links {
        Io(std::io::Error) #[doc = "I/O error"];
    }

    errors {

    }
}
