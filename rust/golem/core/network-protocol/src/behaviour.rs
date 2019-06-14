use crate::custom_proto::ProtocolMessage;
use crate::ProtocolId;
use libp2p::core::Multiaddr;
use libp2p::PeerId;
use std::collections::HashSet;

pub trait BehaviourEvent {
    // Deliberately empty
}

pub trait DiscoveryNetBehaviour {
    /// Report discovery of PeerIds. Not guaranteed to be unique.
    fn add_discovered_nodes(&mut self, nodes: impl Iterator<Item = PeerId>);
}

pub trait PeerNetBehaviour {
    /// Returns a vector of supported protocol identifiers.
    fn protocol_ids(&self) -> Vec<ProtocolId>;
    /// Returns a set of peers that we have an open channel with.
    fn open_peers(&self) -> HashSet<PeerId>;

    /// Returns true if we have a channel open with this node.
    fn is_open(&self, peer_id: &PeerId) -> bool;
    /// Returns true if we try to open protocols with the given peer.
    fn is_enabled(&self, peer_id: &PeerId) -> bool;

    /// Connects to multiaddr.
    fn connect(&mut self, multiaddr: &Multiaddr);
    /// Connects to peer.
    fn connect_to_peer(&mut self, peer_id: &PeerId);
    /// Connects from a peer.
    fn disconnect_peer(&mut self, peer_id: &PeerId);

    /// Sends a message to a peer.
    fn send_message(
        &mut self,
        protocol_id: &ProtocolId,
        peer_id: &PeerId,
        message: ProtocolMessage,
    );
}
