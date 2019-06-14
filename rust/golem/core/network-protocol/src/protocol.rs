use log::error;
use std::collections::HashSet;

use libp2p::core::swarm::{NetworkBehaviourAction, NetworkBehaviourEventProcess};
use libp2p::core::Multiaddr;
use libp2p::{NetworkBehaviour, PeerId};

use crate::behaviour::{DiscoveryNetBehaviour, PeerNetBehaviour};
use crate::custom_proto::{CustomProto, CustomProtoOut, ProtocolMessage, RegisteredProtocol};
use crate::ProtocolId;
use futures::Async;
use tokio::io::{AsyncRead, AsyncWrite};

#[derive(NetworkBehaviour)]
#[behaviour(out_event = "CustomProtoOut", poll_method = "poll")]
pub struct Protocol<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    // The NetworkBehaviour macro requires the protocols to be defined as struct properties
    golem_p2p: CustomProto<TSubstream>,
    golem_dof: CustomProto<TSubstream>,
    #[behaviour(ignore)]
    events: Vec<CustomProtoOut>,
}

impl<TSubstream> Protocol<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    pub fn new() -> Self {
        Protocol {
            golem_p2p: golem_p2p_protocol(),
            golem_dof: golem_dof_protocol(),
            events: Vec::new(),
        }
    }

    fn poll<TEv>(&mut self) -> Async<NetworkBehaviourAction<TEv, CustomProtoOut>> {
        if !self.events.is_empty() {
            return Async::Ready(NetworkBehaviourAction::GenerateEvent(self.events.remove(0)));
        }

        Async::NotReady
    }
}

// TODO: proc macro
impl<TSubstream> PeerNetBehaviour for Protocol<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn protocol_ids(&self) -> Vec<ProtocolId> {
        vec![self.golem_p2p.id(), self.golem_dof.id()]
    }

    fn open_peers(&self) -> HashSet<PeerId> {
        let mut peers: HashSet<PeerId> = HashSet::new();
        peers.extend(self.golem_p2p.open_peers());
        peers.extend(self.golem_dof.open_peers());
        peers
    }

    fn is_open(&self, peer_id: &PeerId) -> bool {
        let mut result = true;
        result &= self.golem_p2p.is_open(peer_id);
        result &= self.golem_dof.is_open(peer_id);
        result
    }

    fn is_enabled(&self, peer_id: &PeerId) -> bool {
        let mut result = true;
        result &= self.golem_p2p.is_enabled(peer_id);
        result &= self.golem_dof.is_enabled(peer_id);
        result
    }

    fn connect(&mut self, multiaddr: &Multiaddr) {
        self.golem_p2p.connect(multiaddr);
        self.golem_dof.connect(multiaddr);
    }

    fn connect_to_peer(&mut self, peer_id: &PeerId) {
        self.golem_p2p.connect_to_peer(peer_id);
        self.golem_dof.connect_to_peer(peer_id);
    }

    fn disconnect_peer(&mut self, peer_id: &PeerId) {
        self.golem_p2p.disconnect_peer(peer_id);
        self.golem_dof.disconnect_peer(peer_id);
    }

    fn send_message(
        &mut self,
        protocol_id: &ProtocolId,
        peer_id: &PeerId,
        message: ProtocolMessage,
    ) {
        let protocol = if *protocol_id == self.golem_p2p.id() {
            Some(&mut self.golem_p2p)
        } else if *protocol_id == self.golem_dof.id() {
            Some(&mut self.golem_dof)
        } else {
            None
        };

        match protocol {
            Some(protocol) => {
                protocol.send_message(protocol_id, peer_id, message);
            }
            None => error!("Cannot send a message: unknown protocol: {:?}", protocol_id),
        }
    }
}

// TODO: proc macro
impl<TSubstream> DiscoveryNetBehaviour for Protocol<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn add_discovered_nodes(&mut self, nodes: impl Iterator<Item = PeerId>) {
        let nodes: Vec<PeerId> = nodes.map(|p| p.clone()).collect();
        self.golem_p2p.add_discovered_nodes(nodes.iter().cloned());
        self.golem_dof.add_discovered_nodes(nodes.iter().cloned());
    }
}

impl<TSubstream> NetworkBehaviourEventProcess<CustomProtoOut> for Protocol<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn inject_event(&mut self, event: CustomProtoOut) {
        self.events.push(event);
    }
}

/// P2P protocol
fn golem_p2p_protocol<TSubstream>() -> CustomProto<TSubstream> {
    let protocol_id = b"p2p";
    let versions = vec![1];
    CustomProto::new(RegisteredProtocol::new(*protocol_id, versions))
}

/// Demand-Offer protocol
fn golem_dof_protocol<TSubstream>() -> CustomProto<TSubstream> {
    let protocol_id = b"dof";
    let versions = vec![1];
    CustomProto::new(RegisteredProtocol::new(*protocol_id, versions))
}
