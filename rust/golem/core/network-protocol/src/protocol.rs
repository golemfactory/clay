use log::error;
use std::collections::HashSet;

use libp2p::core::swarm::{NetworkBehaviourAction, NetworkBehaviourEventProcess};
use libp2p::core::Multiaddr;
use libp2p::{NetworkBehaviour, PeerId};

use network_protocol_derive::{DiscoveryNetBehaviour, PeerNetBehaviour};

use crate::custom_proto::{CustomProto, CustomProtoOut, ProtocolMessage, RegisteredProtocol};
use crate::ProtocolId;
use futures::Async;
use tokio::io::{AsyncRead, AsyncWrite};

#[derive(NetworkBehaviour, DiscoveryNetBehaviour, PeerNetBehaviour)]
#[behaviour(out_event = "CustomProtoOut", poll_method = "poll")]
pub struct Protocol<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    // Because of the applied derive macros, protocols have to be defined as struct members
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
