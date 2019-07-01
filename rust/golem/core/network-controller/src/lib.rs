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
    DisconnectPeer(PeerId, ProtocolId),
    SendMessage(PeerId, UserMessage),
    Stop,
}
