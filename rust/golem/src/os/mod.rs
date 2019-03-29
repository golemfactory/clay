pub mod error;

#[cfg(windows)]
pub mod windows;

#[cfg(not(windows))]
pub mod windows {
    use crate::os::error::OSError;

    pub fn empty_working_sets() -> Result<(), OSError> {
        Err(OSError::new("Unsupported OS"))
    }
}
