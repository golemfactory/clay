use crate::message::UserMessage;
use crate::PeerId;
use network_libp2p::{ConnectedPoint, Multiaddr, ProtocolId, PublicKey};

#[derive(Clone, Debug)]
pub enum NetworkEvent {
    /// Started listening on address
    Listening(Vec<Multiaddr>),
    /// Stopped listening
    Terminated,
    /// Peer connected
    Connected(PeerId, ConnectedPoint, PublicKey),
    /// Peer disconnected
    Disconnected(PeerId, ConnectedPoint),
    /// Message received from peer
    Message(PeerId, ConnectedPoint, UserMessage),
    /// Peer is unable to process sent messages
    Clogged(PeerId, Option<UserMessage>),
}
