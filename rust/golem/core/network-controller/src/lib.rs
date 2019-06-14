extern crate crossbeam_channel;
#[macro_use]
extern crate lazy_static;
#[macro_use]
extern crate serde_derive;

mod codec;
mod controller;
pub mod error;
pub mod event;
mod message;

pub use self::controller::NetworkController;
pub use self::message::UserMessage;
pub use network_libp2p::*;

#[derive(Clone, Debug)]
pub enum ClientRequest {
    Connect(Multiaddr),
    ConnectToPeer(PeerId),
    DisconnectPeer(PeerId),
    SendMessage(PeerId, UserMessage),
    Stop,
}

unsafe impl Send for ClientRequest {}
unsafe impl Sync for ClientRequest {}
