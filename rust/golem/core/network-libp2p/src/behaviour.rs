// Copyright 2019 Parity Technologies (UK) Ltd.
// This file is part of Substrate.

// Substrate is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.

// Substrate is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.

// You should have received a copy of the GNU General Public License
// along with Substrate.  If not, see <http://www.gnu.org/licenses/>.

mod debug_info;

use std::{cmp, iter, time::Duration};
use std::collections::HashSet;
use std::collections::hash_map::RandomState;

use futures::prelude::*;
use log::{debug, info, trace, warn};
use tokio_io::{AsyncRead, AsyncWrite};
use tokio_timer::{clock::Clock, Delay};
use void;

#[cfg(not(target_os = "unknown"))]
use libp2p::core::swarm::toggle::Toggle;
use libp2p::core::swarm::{
    self, ConnectedPoint, NetworkBehaviourAction, NetworkBehaviourEventProcess,
    PollParameters,
};
use libp2p::core::{Multiaddr, PeerId, ProtocolsHandler, PublicKey};
use libp2p::kad::{Kademlia, KademliaOut};
#[cfg(not(target_os = "unknown"))]
use libp2p::mdns::{Mdns, MdnsEvent};
use libp2p::NetworkBehaviour;
use parity_multiaddr;

use network_protocol::{Protocol, ProtocolMessage, ProtocolId, DiscoveryNetBehaviour, PeerNetBehaviour, CustomProtoOut};

/// General behaviour of the network.
#[derive(NetworkBehaviour)]
#[behaviour(out_event = "CustomProtoOut", poll_method = "poll")]
pub struct Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    /// Main protocol that handles everything except the discovery and the technicalities.
    protocol: Protocol<TSubstream>,
    /// Periodically pings and identifies the nodes we are connected to, and caches the information
    debug_info: debug_info::DebugInfoBehaviour<TSubstream>,
    /// Discovers nodes of the network. Defined below.
    discovery: DiscoveryBehaviour<TSubstream>,
    /// Discovers nodes on the local network.
    #[cfg(not(target_os = "unknown"))]
    mdns: Toggle<Mdns<TSubstream>>,

    /// Queue of events to produce for the outside.
    #[behaviour(ignore)]
    events: Vec<CustomProtoOut>,
}

impl<TSubstream> Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    /// Builds a new `Behaviour`.
    pub fn new(
        user_agent: String,
        local_public_key: PublicKey,
        enable_mdns: bool,
    ) -> Self {
        let debug_info = debug_info::DebugInfoBehaviour::new(user_agent, local_public_key.clone());
        let kademlia = Kademlia::new(local_public_key.clone().into_peer_id());

        #[cfg(not(target_os = "unknown"))]
        let mdns = if enable_mdns {
            match Mdns::new() {
                Ok(mdns) => Some(mdns).into(),
                Err(err) => {
                    warn!(target: crate::LOG_TARGET, "Failed to initialize mDNS: {:?}", err);
                    None.into()
                }
            }
        } else {
            None.into()
        };

        let clock = Clock::new();
        Behaviour {
            protocol: Protocol::new(),
            debug_info,
            discovery: DiscoveryBehaviour {
                user_defined: Vec::new(),
                kademlia,
                next_kad_random_query: Delay::new(clock.now()),
                duration_to_next_kad: Duration::from_secs(1),
                clock,
                local_peer_id: local_public_key.into_peer_id(),
            },
            #[cfg(not(target_os = "unknown"))]
            mdns,
            events: Vec::new(),
        }
    }

    /// Returns the list of nodes that we know exist in the network.
    pub fn known_peers(&mut self) -> impl Iterator<Item = &PeerId> {
        self.discovery.kademlia.kbuckets_entries()
    }

    /// Adds a hard-coded address for the given peer, that never expires.
    pub fn add_known_address(&mut self, peer_id: PeerId, addr: Multiaddr) {
        if self
            .discovery
            .user_defined
            .iter()
            .all(|(p, a)| *p != peer_id && *a != addr)
        {
            self.discovery.user_defined.push((peer_id, addr));
        }
    }

    /// Borrows `self` and returns a struct giving access to the information about a node.
    ///
    /// Returns `None` if we don't know anything about this node. Always returns `Some` for nodes
    /// we're connected to, meaning that if `None` is returned then we're not connected to that
    /// node.
    pub fn node(&self, peer_id: &PeerId) -> Option<debug_info::Node> {
        self.debug_info.node(peer_id)
    }
}

impl<TSubstream> DiscoveryNetBehaviour for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn add_discovered_nodes(&mut self, nodes: impl Iterator<Item = PeerId>) {
        self.protocol.add_discovered_nodes(nodes);
    }
}

impl<TSubstream> PeerNetBehaviour for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn protocol_ids(&self) -> Vec<ProtocolId> {
        self.protocol.protocol_ids()
    }

    fn open_peers(&self) -> HashSet<PeerId, RandomState> {
        self.protocol.open_peers()
    }

    fn is_open(&self, peer_id: &PeerId) -> bool {
        self.protocol.is_open(peer_id)
    }

    fn is_enabled(&self, peer_id: &PeerId) -> bool {
        self.protocol.is_enabled(peer_id)
    }

    fn connect(&mut self, multiaddr: &Multiaddr) {
        self.protocol.connect(multiaddr);
    }

    fn connect_to_peer(&mut self, peer_id: &PeerId) {
        self.protocol.connect_to_peer(peer_id);
    }

    fn disconnect_peer(&mut self, peer_id: &PeerId, protocol_id: &ProtocolId) {
        self.protocol.disconnect_peer(peer_id, protocol_id);
    }

    fn send_message(&mut self, peer_id: &PeerId, protocol_id: &ProtocolId, message: ProtocolMessage) {
        self.protocol.send_message(peer_id, protocol_id, message);
    }
}

impl<TSubstream> NetworkBehaviourEventProcess<void::Void>
    for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn inject_event(&mut self, event: void::Void) {
        void::unreachable(event)
    }
}

impl<TSubstream> NetworkBehaviourEventProcess<CustomProtoOut>
    for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn inject_event(
        &mut self,
        event: CustomProtoOut,
    ) {
        self.events.push(event);
    }
}

impl<TSubstream> NetworkBehaviourEventProcess<debug_info::DebugInfoEvent>
    for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn inject_event(&mut self, event: debug_info::DebugInfoEvent) {
        let debug_info::DebugInfoEvent::Identified { peer_id, mut info } = event;
        if !info.protocol_version.contains(crate::PROTOCOL_NAME) {
            warn!(
                target: crate::LOG_TARGET,
                "Connected to a non-{:?} node: {:?}",
                crate::PROTOCOL_NAME,
                info
            );
        }
        if info.listen_addrs.len() > 30 {
            warn!(
                target: crate::LOG_TARGET,
                "Node {:?} has reported more than 30 addresses; \
                 it is identified by {:?} and {:?}",
                peer_id,
                info.protocol_version,
                info.agent_version
            );
            info.listen_addrs.truncate(30);
        }
        for addr in &info.listen_addrs {
            self.discovery.kademlia.add_address(&peer_id, addr.clone());
        }
        self.protocol
            .add_discovered_nodes(iter::once(peer_id.clone()));
    }
}

impl<TSubstream> NetworkBehaviourEventProcess<KademliaOut>
    for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn inject_event(&mut self, out: KademliaOut) {
        match out {
            KademliaOut::Discovered { .. } => {}
            KademliaOut::KBucketAdded { peer_id, .. } => {
                self.protocol.add_discovered_nodes(iter::once(peer_id));
            }
            KademliaOut::FindNodeResult { key, closer_peers } => {
                trace!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Query for {:?} yielded {:?} results",
                    key,
                    closer_peers.len()
                );
                if closer_peers.is_empty() {
                    debug!(
                        target: crate::LOG_TARGET,
                        "Libp2p => Random Kademlia query has yielded empty \
                         results"
                    );
                }
            }
            // We never start any other type of query.
            KademliaOut::GetProvidersResult { .. } => {}
            KademliaOut::GetValueResult(_) => {}
            KademliaOut::PutValueResult(_) => {}
        }
    }
}

#[cfg(not(target_os = "unknown"))]
impl<TSubstream> NetworkBehaviourEventProcess<MdnsEvent>
    for Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    fn inject_event(&mut self, event: MdnsEvent) {
        match event {
            MdnsEvent::Discovered(list) => {
                self.protocol
                    .add_discovered_nodes(list.into_iter().map(|(peer_id, _)| peer_id));
            }
            MdnsEvent::Expired(_) => {}
        }
    }
}

impl<TSubstream> Behaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    pub fn poll<TEv>(
        &mut self,
    ) -> Async<NetworkBehaviourAction<TEv, CustomProtoOut>> {
        if !self.events.is_empty() {
            return Async::Ready(NetworkBehaviourAction::GenerateEvent(self.events.remove(0)));
        }

        Async::NotReady
    }
}

/// Implementation of `NetworkBehaviour` that discovers the nodes on the network.
pub struct DiscoveryBehaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    /// User-defined list of nodes and their addresses. Typically includes bootstrap nodes and
    /// reserved nodes.
    user_defined: Vec<(PeerId, Multiaddr)>,
    /// Kademlia requests and answers.
    kademlia: Kademlia<TSubstream>,
    /// Stream that fires when we need to perform the next random Kademlia query.
    next_kad_random_query: Delay,
    /// After `next_kad_random_query` triggers, the next one triggers after this duration.
    duration_to_next_kad: Duration,
    /// `Clock` instance that uses the current execution context's source of time.
    clock: Clock,
    /// Identity of our local node.
    local_peer_id: PeerId,
}

impl<TSubstream> swarm::NetworkBehaviour for DiscoveryBehaviour<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    type ProtocolsHandler = <Kademlia<TSubstream> as swarm::NetworkBehaviour>::ProtocolsHandler;
    type OutEvent = <Kademlia<TSubstream> as swarm::NetworkBehaviour>::OutEvent;

    fn new_handler(&mut self) -> Self::ProtocolsHandler {
        swarm::NetworkBehaviour::new_handler(&mut self.kademlia)
    }

    fn addresses_of_peer(&mut self, peer_id: &PeerId) -> Vec<Multiaddr> {
        let mut list = self
            .user_defined
            .iter()
            .filter_map(|(p, a)| if p == peer_id { Some(a.clone()) } else { None })
            .collect::<Vec<_>>();
        list.extend(self.kademlia.addresses_of_peer(peer_id));
        trace!(
            target: crate::LOG_TARGET,
            "Addresses of {:?} are {:?}",
            peer_id,
            list
        );
        if list.is_empty() {
            if self.kademlia.kbuckets_entries().any(|p| p == peer_id) {
                debug!(
                    target: crate::LOG_TARGET,
                    "Requested dialing to {:?} (peer in k-buckets), \
                     and no address was found",
                    peer_id
                );
            } else {
                debug!(
                    target: crate::LOG_TARGET,
                    "Requested dialing to {:?} (peer not in k-buckets), \
                     and no address was found",
                    peer_id
                );
            }
        }
        list
    }

    fn inject_connected(&mut self, peer_id: PeerId, endpoint: ConnectedPoint) {
        swarm::NetworkBehaviour::inject_connected(&mut self.kademlia, peer_id, endpoint)
    }

    fn inject_disconnected(&mut self, peer_id: &PeerId, endpoint: ConnectedPoint) {
        swarm::NetworkBehaviour::inject_disconnected(&mut self.kademlia, peer_id, endpoint)
    }

    fn inject_replaced(&mut self, peer_id: PeerId, closed: ConnectedPoint, opened: ConnectedPoint) {
        swarm::NetworkBehaviour::inject_replaced(&mut self.kademlia, peer_id, closed, opened)
    }

    fn inject_node_event(
        &mut self,
        peer_id: PeerId,
        event: <Self::ProtocolsHandler as ProtocolsHandler>::OutEvent,
    ) {
        swarm::NetworkBehaviour::inject_node_event(&mut self.kademlia, peer_id, event)
    }

    fn inject_expired_listen_addr(&mut self, addr: &Multiaddr) {
        info!(target: crate::LOG_TARGET, "No longer listening on {}", addr);
    }

    fn inject_new_external_addr(&mut self, addr: &Multiaddr) {
        let new_addr = addr
            .clone()
            .with(parity_multiaddr::Protocol::P2p(self.local_peer_id.clone().into()));
        info!(
            target: crate::LOG_TARGET,
            "Discovered new external address for our node: {}", new_addr
        );
    }

    fn poll(
        &mut self,
        params: &mut impl PollParameters,
    ) -> Async<
        NetworkBehaviourAction<
            <Self::ProtocolsHandler as ProtocolsHandler>::InEvent,
            Self::OutEvent,
        >,
    > {
        // Poll Kademlia.
        match self.kademlia.poll(params) {
            Async::Ready(action) => return Async::Ready(action),
            Async::NotReady => (),
        }

        // Poll the stream that fires when we need to start a random Kademlia query.
        loop {
            match self.next_kad_random_query.poll() {
                Ok(Async::NotReady) => break,
                Ok(Async::Ready(_)) => {
                    let random_peer_id = PeerId::random();
                    debug!(
                        target: crate::LOG_TARGET,
                        "Libp2p <= Starting random Kademlia request for \
                         {:?}",
                        random_peer_id
                    );
                    self.kademlia.find_node(random_peer_id);

                    // Reset the `Delay` to the next random.
                    self.next_kad_random_query
                        .reset(self.clock.now() + self.duration_to_next_kad);
                    self.duration_to_next_kad =
                        cmp::min(self.duration_to_next_kad * 2, Duration::from_secs(60));
                }
                Err(err) => {
                    warn!(
                        target: crate::LOG_TARGET,
                        "Kademlia query timer errored: {:?}", err
                    );
                    break;
                }
            }
        }

        Async::NotReady
    }
}
