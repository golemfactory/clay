extern crate crossbeam_channel;
#[macro_use]
extern crate lazy_static;
#[macro_use]
extern crate serde_derive;

pub mod codec;
pub mod controller;
pub mod error;
pub mod event;
pub mod message;
pub mod peer;

pub use self::controller::*;

pub const PROTOCOL_VERSION: u32 = 1;
