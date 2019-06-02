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

use std::thread;
use futures::sync::oneshot;

pub use self::controller::*;
pub use crate::message::NetworkMessage;

pub const PROTOCOL_VERSION: u32 = 1;

#[derive(Clone)]
pub enum ClientRequest {
	Connect(Multiaddr),
	ConnectToPeer(PeerId),
	DisconnectPeer(PeerId),
	SendMessage(PeerId, NetworkMessage),
	Stop,
}

unsafe impl Send for ClientRequest {}
unsafe impl Sync for ClientRequest {}

pub struct ThreadLink {
	pub handle: thread::JoinHandle<()>,
	pub close_tx: oneshot::Sender<()>,
}
