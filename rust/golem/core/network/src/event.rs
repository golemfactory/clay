use crate::PeerId;
use crate::message::NetworkMessage;
use network_libp2p::{Multiaddr, ConnectedPoint, PublicKey};

#[derive(Clone, Debug)]
pub enum NetworkEvent {
	/// Started listening on address
	Listening(Vec<Multiaddr>),
	/// Stopped listening
	Terminated,
	/// Peer connected
	Connected(PeerId, PublicKey, ConnectedPoint),
	/// Peer disconnected
	Disconnected(PeerId, ConnectedPoint),
	/// Message received from peer
	Message(PeerId, ConnectedPoint, NetworkMessage),
	/// Peer is unable to process sent messages
	Clogged(PeerId, Option<NetworkMessage>),
}
