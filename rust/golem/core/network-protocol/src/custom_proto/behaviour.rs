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

use crate::behaviour::{BehaviourEvent, DiscoveryNetBehaviour, PeerNetBehaviour};
use crate::custom_proto::handler::{
    CustomProtoHandlerIn, CustomProtoHandlerOut, CustomProtoHandlerProto,
};
use crate::custom_proto::upgrade::RegisteredProtocol;
use crate::custom_proto::ProtocolMessage;
use crate::ProtocolId;

use fnv::FnvHashMap;
use futures::prelude::*;
use libp2p::core::swarm::{
    ConnectedPoint, NetworkBehaviour, NetworkBehaviourAction, PollParameters,
};
use libp2p::core::{Multiaddr, PeerId};
use log::{debug, error, trace, warn};
use smallvec::SmallVec;
use std::collections::HashSet;
use std::{
    borrow::Cow, cmp, collections::hash_map::Entry, error, marker::PhantomData, mem,
    time::Duration, time::Instant,
};
use tokio_io::{AsyncRead, AsyncWrite};
use tokio_timer::clock::Clock;

#[derive(Debug, Copy, Clone, PartialEq, Eq, Hash)]
pub struct IncomingIndex(pub u64);

impl From<u64> for IncomingIndex {
    fn from(val: u64) -> IncomingIndex {
        IncomingIndex(val)
    }
}

/// Network behaviour that handles opening substreams for custom protocols with other nodes.
///
/// ## How it works
///
/// The role of the `CustomProto` is to synchronize the following components:
///
/// - The libp2p swarm that opens new connections and reports disconnects.
/// - The connection handler (see `handler.rs`) that handles individual connections.
/// - The external API, that requires knowledge of the links that have been established.
///
/// Each connection handler can be in four different states: Enabled+Open, Enabled+Closed,
/// Disabled+Open, or Disabled+Closed.
///
/// However a connection handler only exists if we are actually connected to a node. What this
/// means is that there are six possible states for each node: Disconnected, Dialing (trying to
/// reach it), Enabled+Open, Enabled+Closed, Disabled+open, Disabled+Closed.
///
/// Additionally, there also exists a "banning" system. If we fail to dial a node, we "ban" it for
/// a few seconds.
/// Note that this "banning" system is not an actual ban. If a "banned" node tries to connect to
/// us, we accept the connection. The "banning" system is only about delaying dialing attempts.
///
pub struct CustomProto<TSubstream> {
    /// List of protocols to open with peers. Never modified.
    protocol: RegisteredProtocol,

    /// List of peers in our state.
    peers: FnvHashMap<PeerId, PeerState>,

    /// We generate indices to identify incoming connections. This is the next value for the index
    /// to use when a connection is incoming.
    next_incoming_index: IncomingIndex,

    /// Events to produce from `poll()`.
    events: SmallVec<[NetworkBehaviourAction<CustomProtoHandlerIn, CustomProtoOut>; 4]>,

    /// Marker to pin the generics.
    marker: PhantomData<TSubstream>,

    /// `Clock` instance that uses the current execution context's source of time.
    clock: Clock,
}

/// State of a peer we're connected to.
#[derive(Debug)]
enum PeerState {
    /// State is poisoned. This is a temporary state for a peer and we should always switch back
    /// to it later. If it is found in the wild, that means there was either a panic or a bug in
    /// the state machine code.
    Poisoned,

    /// The peer misbehaved.
    Banned {
        /// Until when the node is banned.
        until: Instant,
        /// Whether we initiated the connection
        initiator: bool,
    },

    /// The user requested that we connect to this peer. We are not connected to this node.
    PendingRequest {
        /// When to actually start dialing.
        timer: tokio_timer::Delay,
    },

    /// The user requested that we connect to this peer. We are currently dialing this peer.
    Requested,

    /// We are connected to this peer but the connection was refused. This peer can still perform
    /// Kademlia queries and such, but should get disconnected in a few seconds.
    Disabled {
        /// How we are connected to this peer.
        connected_point: ConnectedPoint,
        /// If true, we still have a custom protocol open with it. It will likely get closed in
        /// a short amount of time, but we need to keep the information in order to not have a
        /// state mismatch.
        open: bool,
        /// If `Some`, the node is banned until the given `Instant`.
        banned_until: Option<Instant>,
    },

    /// We are connected to this peer but we are not opening any substream. The handler
    /// will be enabled when `timer` fires. This peer can still perform Kademlia queries and such,
    /// but should get disconnected in a few seconds.
    DisabledPendingEnable {
        /// How we are connected to this peer.
        connected_point: ConnectedPoint,
        /// If true, we still have a custom protocol open with it. It will likely get closed in
        /// a short amount of time, but we need to keep the information in order to not have a
        /// state mismatch.
        open: bool,
        /// When to enable this remote.
        timer: tokio_timer::Delay,
    },

    /// We are connected to this peer. The handler is in the enabled state.
    Enabled {
        /// How we are connected to this peer.
        connected_point: ConnectedPoint,
        /// If true, we have a custom protocol open with this peer.
        open: bool,
    },
}

impl PeerState {
    /// True if we have an open channel with that node.
    fn is_open(&self) -> bool {
        match self {
            PeerState::Poisoned => false,
            PeerState::Banned { .. } => false,
            PeerState::PendingRequest { .. } => false,
            PeerState::Requested => false,
            PeerState::Disabled { open, .. } => *open,
            PeerState::DisabledPendingEnable { open, .. } => *open,
            PeerState::Enabled { open, .. } => *open,
        }
    }
}

/// Event that can be emitted by the `CustomProto`.
#[derive(Debug)]
pub enum CustomProtoOut {
    /// Opened a custom protocol with the remote.
    CustomProtocolOpen {
        /// Version of the protocol that has been opened.
        version: u8,
        /// Id of the node we have opened a connection with.
        peer_id: PeerId,
        /// Endpoint used for this custom protocol.
        endpoint: ConnectedPoint,
    },

    /// Closed a custom protocol with the remote.
    CustomProtocolClosed {
        /// Id of the peer we were connected to.
        peer_id: PeerId,
        /// Endpoint used for this custom protocol.
        endpoint: ConnectedPoint,
        /// Reason why the substream closed. If `Ok`, then it's a graceful exit (EOF).
        reason: Cow<'static, str>,
    },

    /// Receives a message on a custom protocol substream.
    CustomMessage {
        /// Id of the peer the message came from.
        peer_id: PeerId,
        /// Endpoint used for this custom protocol.
        endpoint: ConnectedPoint,
        /// Message that has been received.
        message: ProtocolMessage,
    },

    /// The substream used by the protocol is pretty large. We should print avoid sending more
    /// messages on it if possible.
    Clogged {
        /// Id of the peer which is clogged.
        peer_id: PeerId,
        /// Copy of the messages that are within the buffer, for further diagnostic.
        messages: Vec<ProtocolMessage>,
    },
}

impl BehaviourEvent for CustomProtoOut {}

impl<TSubstream> CustomProto<TSubstream> {
    /// Creates a `CustomProtos`.
    pub fn new(protocol: RegisteredProtocol) -> Self {
        CustomProto {
            protocol,
            peers: FnvHashMap::default(),
            next_incoming_index: IncomingIndex(0),
            events: SmallVec::new(),
            marker: PhantomData,
            clock: Clock::new(),
        }
    }

    pub fn id(&self) -> ProtocolId {
        self.protocol.id()
    }

    /// Inner implementation of `disconnect_peer`. If `ban` is `Some`, we ban the node for the
    /// specific duration.
    fn disconnect_peer_inner(&mut self, peer_id: &PeerId, ban: Option<Duration>) {
        let mut entry = if let Entry::Occupied(entry) = self.peers.entry(peer_id.clone()) {
            entry
        } else {
            return;
        };

        match mem::replace(entry.get_mut(), PeerState::Poisoned) {
            // We're not connected anyway.
            st @ PeerState::Disabled { .. } => *entry.into_mut() = st,
            st @ PeerState::Requested => *entry.into_mut() = st,
            st @ PeerState::PendingRequest { .. } => *entry.into_mut() = st,
            st @ PeerState::Banned { .. } => *entry.into_mut() = st,

            // DisabledPendingEnable => Disabled.
            PeerState::DisabledPendingEnable {
                open,
                connected_point,
                timer,
            } => {
                let banned_until = Some(if let Some(ban) = ban {
                    cmp::max(timer.deadline(), self.clock.now() + ban)
                } else {
                    timer.deadline()
                });
                *entry.into_mut() = PeerState::Disabled {
                    open,
                    connected_point,
                    banned_until,
                }
            }

            // Enabled => Disabled.
            PeerState::Enabled {
                open,
                connected_point,
            } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) <= Disable", peer_id
                );
                self.events.push(NetworkBehaviourAction::SendEvent {
                    peer_id: peer_id.clone(),
                    event: CustomProtoHandlerIn::Disable,
                });
                let clock = &self.clock;
                let banned_until = ban.map(|dur| clock.now() + dur);
                *entry.into_mut() = PeerState::Disabled {
                    open,
                    connected_point,
                    banned_until,
                }
            }

            PeerState::Poisoned => error!(
                target: crate::LOG_TARGET,
                "State of {:?} is poisoned", peer_id
            ),
        }
    }

    fn requested_dial(&mut self, address: Multiaddr) {
        self.events
            .push(NetworkBehaviourAction::DialAddress { address });
    }

    /// Function that is called when the peer manager wants us to connect to a node.
    fn requested_connect(&mut self, peer_id: PeerId) {
        let mut occ_entry = match self.peers.entry(peer_id) {
            Entry::Occupied(entry) => entry,
            Entry::Vacant(entry) => {
                // If there's no entry in `self.peers`, start dialing.
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Starting to connect",
                    entry.key()
                );
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p <= Dial {:?}",
                    entry.key()
                );
                self.events.push(NetworkBehaviourAction::DialPeer {
                    peer_id: entry.key().clone(),
                });
                entry.insert(PeerState::Requested);
                return;
            }
        };

        match mem::replace(occ_entry.get_mut(), PeerState::Poisoned) {
            PeerState::Banned { ref until, .. } if *until > self.clock.now() => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Will start to connect at \
                     until {:?}",
                    occ_entry.key(),
                    until
                );
                *occ_entry.into_mut() = PeerState::PendingRequest {
                    timer: tokio_timer::Delay::new(until.clone()),
                };
            }

            PeerState::Banned { .. } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Starting to connect",
                    occ_entry.key()
                );
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p <= Dial {:?}",
                    occ_entry.key()
                );
                self.events.push(NetworkBehaviourAction::DialPeer {
                    peer_id: occ_entry.key().clone(),
                });
                *occ_entry.into_mut() = PeerState::Requested;
            }

            PeerState::Disabled {
                open,
                ref connected_point,
                banned_until: Some(ref banned),
            } if *banned > self.clock.now() => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Has idle connection through \
                     {:?} but node is banned until {:?}",
                    occ_entry.key(),
                    connected_point,
                    banned
                );
                *occ_entry.into_mut() = PeerState::DisabledPendingEnable {
                    connected_point: connected_point.clone(),
                    open,
                    timer: tokio_timer::Delay::new(banned.clone()),
                };
            }

            PeerState::Disabled {
                open,
                connected_point,
                banned_until: _,
            } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Enabling previously-idle \
                     connection through {:?}",
                    occ_entry.key(),
                    connected_point
                );
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) <= Enable",
                    occ_entry.key()
                );
                self.events.push(NetworkBehaviourAction::SendEvent {
                    peer_id: occ_entry.key().clone(),
                    event: CustomProtoHandlerIn::Enable(connected_point.clone().into()),
                });
                *occ_entry.into_mut() = PeerState::Enabled {
                    connected_point,
                    open,
                };
            }

            st @ PeerState::Enabled { .. } => {
                warn!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Already connected to this \
                     peer",
                    occ_entry.key()
                );
                *occ_entry.into_mut() = st;
            }
            st @ PeerState::DisabledPendingEnable { .. } => {
                warn!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Already have an idle \
                     connection to this peer and waiting to enable it",
                    occ_entry.key()
                );
                *occ_entry.into_mut() = st;
            }
            st @ PeerState::Requested { .. } | st @ PeerState::PendingRequest { .. } => {
                warn!(
                    target: crate::LOG_TARGET,
                    "User => Connect({:?}): Received a previous \
                     request for that peer",
                    occ_entry.key()
                );
                *occ_entry.into_mut() = st;
            }

            PeerState::Poisoned => error!(
                target: crate::LOG_TARGET,
                "State of {:?} is poisoned",
                occ_entry.key()
            ),
        }
    }

    /// Function that is called when the peer manager wants us to disconnect from a node.
    fn requested_disconnect(&mut self, peer_id: PeerId) {
        let mut entry = match self.peers.entry(peer_id) {
            Entry::Occupied(entry) => entry,
            Entry::Vacant(entry) => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Drop({:?}): Node already disabled",
                    entry.key()
                );
                return;
            }
        };

        match mem::replace(entry.get_mut(), PeerState::Poisoned) {
            st @ PeerState::Disabled { .. } | st @ PeerState::Banned { .. } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Drop({:?}): Node already disabled",
                    entry.key()
                );
                *entry.into_mut() = st;
            }

            PeerState::DisabledPendingEnable {
                open,
                connected_point,
                timer,
            } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Drop({:?}): Interrupting pending \
                     enable",
                    entry.key()
                );
                *entry.into_mut() = PeerState::Disabled {
                    open,
                    connected_point,
                    banned_until: Some(timer.deadline()),
                };
            }

            PeerState::Enabled {
                open,
                connected_point,
            } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Drop({:?}): Disabling connection",
                    entry.key()
                );
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) <= Disable",
                    entry.key()
                );
                self.events.push(NetworkBehaviourAction::SendEvent {
                    peer_id: entry.key().clone(),
                    event: CustomProtoHandlerIn::Disable,
                });
                *entry.into_mut() = PeerState::Disabled {
                    open,
                    connected_point,
                    banned_until: None,
                }
            }
            PeerState::Requested => {
                // We don't cancel dialing. Libp2p doesn't expose that on purpose, as other
                // sub-systems (such as the discovery mechanism) may require dialing this node as
                // well at the same time.
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Drop({:?}): Was not yet connected",
                    entry.key()
                );
                entry.remove();
            }
            PeerState::PendingRequest { timer } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "User => Drop({:?}): Was not yet connected",
                    entry.key()
                );
                *entry.into_mut() = PeerState::Banned {
                    until: timer.deadline(),
                    initiator: true,
                }
            }

            PeerState::Poisoned => error!(
                target: crate::LOG_TARGET,
                "State of {:?} is poisoned",
                entry.key()
            ),
        }
    }

    fn peer_endpoint(&self, source: &PeerId) -> Option<ConnectedPoint> {
        match self.peers.get(&source) {
            Some(PeerState::Enabled {
                ref connected_point,
                ..
            })
            | Some(PeerState::Disabled {
                ref connected_point,
                ..
            })
            | Some(PeerState::DisabledPendingEnable {
                ref connected_point,
                ..
            }) => Some(connected_point.clone()),
            _ => None,
        }
    }
}

impl<TSubstream> DiscoveryNetBehaviour for CustomProto<TSubstream> {
    fn add_discovered_nodes(&mut self, _peer_ids: impl Iterator<Item = PeerId>) {}
}

impl<TSubstream> PeerNetBehaviour for CustomProto<TSubstream> {
    #[inline]
    fn protocol_ids(&self) -> Vec<ProtocolId> {
        vec![self.protocol.id()]
    }

    fn open_peers(&self) -> HashSet<PeerId> {
        self.peers
            .iter()
            .filter(|(_, state)| state.is_open())
            .map(|(id, _)| id)
            .cloned()
            .collect()
    }

    fn is_open(&self, peer_id: &PeerId) -> bool {
        self.peers
            .get(peer_id)
            .map(|p| p.is_open())
            .unwrap_or(false)
    }

    fn is_enabled(&self, peer_id: &PeerId) -> bool {
        match self.peers.get(peer_id) {
            None => false,
            Some(PeerState::Disabled { .. }) => false,
            Some(PeerState::DisabledPendingEnable { .. }) => false,
            Some(PeerState::Enabled { .. }) => true,
            Some(PeerState::Requested) => false,
            Some(PeerState::PendingRequest { .. }) => false,
            Some(PeerState::Banned { .. }) => false,
            Some(PeerState::Poisoned) => false,
        }
    }

    #[inline]
    fn connect(&mut self, multiaddr: &Multiaddr) {
        debug!(
            target: crate::LOG_TARGET,
            "External API => Dial {:?}", multiaddr
        );
        self.requested_dial(multiaddr.clone());
    }

    #[inline]
    fn connect_to_peer(&mut self, peer_id: &PeerId) {
        debug!(
            target: crate::LOG_TARGET,
            "External API => Connect {:?}", peer_id
        );
        self.requested_connect(peer_id.clone());
    }

    #[inline]
    fn disconnect_peer(&mut self, peer_id: &PeerId, _: &ProtocolId) {
        debug!(
            target: crate::LOG_TARGET,
            "External API => Disconnect {:?}", peer_id
        );
        self.requested_disconnect(peer_id.clone());
    }

    fn send_message(&mut self, peer_id: &PeerId, _: &ProtocolId, message: ProtocolMessage) {
        if !self.is_open(peer_id) {
            warn!(
                target: crate::LOG_TARGET,
                "Session not open, unable to send a packet to {:?}", peer_id
            );
            return;
        }

        trace!(
            target: crate::LOG_TARGET,
            "External API => Packet for {:?}",
            peer_id
        );
        trace!(
            target: crate::LOG_TARGET,
            "Handler({:?}) <= Packet",
            peer_id
        );
        self.events.push(NetworkBehaviourAction::SendEvent {
            peer_id: peer_id.clone(),
            event: CustomProtoHandlerIn::SendCustomMessage { message },
        });
    }
}

impl<TSubstream> NetworkBehaviour for CustomProto<TSubstream>
where
    TSubstream: AsyncRead + AsyncWrite,
{
    type ProtocolsHandler = CustomProtoHandlerProto<TSubstream>;
    type OutEvent = CustomProtoOut;

    fn new_handler(&mut self) -> Self::ProtocolsHandler {
        CustomProtoHandlerProto::new(self.protocol.clone())
    }

    fn addresses_of_peer(&mut self, _: &PeerId) -> Vec<Multiaddr> {
        Vec::new()
    }

    fn inject_connected(&mut self, peer_id: PeerId, connected_point: ConnectedPoint) {
        match (
            self.peers
                .entry(peer_id.clone())
                .or_insert(PeerState::Poisoned),
            connected_point,
        ) {
            (st @ &mut PeerState::Requested, connected_point)
            | (st @ &mut PeerState::PendingRequest { .. }, connected_point) => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Connected({:?}): Connection \
                     requested by User (through {:?})",
                    peer_id,
                    connected_point
                );
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) <= Enable", peer_id
                );
                self.events.push(NetworkBehaviourAction::SendEvent {
                    peer_id: peer_id.clone(),
                    event: CustomProtoHandlerIn::Enable(connected_point.clone().into()),
                });
                *st = PeerState::Enabled {
                    open: false,
                    connected_point,
                };
            }

            // Note: it may seem weird that "Banned" nodes get treated as if there were absent.
            // This is because the word "Banned" means "temporarily prevent outgoing connections to
            // this node", and not "banned" in the sense that we would refuse the node altogether.
            (st @ &mut PeerState::Poisoned, connected_point @ ConnectedPoint::Listener { .. })
            | (
                st @ &mut PeerState::Banned { .. },
                connected_point @ ConnectedPoint::Listener { .. },
            ) => {
                self.next_incoming_index.0 = match self.next_incoming_index.0.checked_add(1) {
                    Some(v) => v,
                    None => {
                        error!(target: crate::LOG_TARGET, "Overflow in next_incoming_index");
                        return;
                    }
                };
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Connected({:?}): (Banned)", peer_id
                );

                self.events.push(NetworkBehaviourAction::SendEvent {
                    peer_id: peer_id.clone(),
                    event: CustomProtoHandlerIn::Enable(connected_point.clone().into()),
                });
                *st = PeerState::Enabled {
                    open: false,
                    connected_point,
                };
            }

            (st @ &mut PeerState::Poisoned, connected_point)
            | (st @ &mut PeerState::Banned { .. }, connected_point) => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Connected({:?})", peer_id
                );

                self.events.push(NetworkBehaviourAction::SendEvent {
                    peer_id: peer_id.clone(),
                    event: CustomProtoHandlerIn::Enable(connected_point.clone().into()),
                });
                *st = PeerState::Enabled {
                    open: false,
                    connected_point,
                };
            }

            st => {
                // This is a serious bug either in this state machine or in libp2p.
                error!(
                    target: crate::LOG_TARGET,
                    "Received inject_connected for \
                     already-connected node; state is {:?}",
                    st
                );
            }
        }
    }

    fn inject_disconnected(&mut self, peer_id: &PeerId, endpoint: ConnectedPoint) {
        match self.peers.remove(peer_id) {
            None
            | Some(PeerState::Requested)
            | Some(PeerState::PendingRequest { .. })
            | Some(PeerState::Banned { .. }) =>
            // This is a serious bug either in this state machine or in libp2p.
            {
                error!(
                    target: crate::LOG_TARGET,
                    "Received inject_disconnected for non-connected \
                     node {:?}",
                    peer_id
                )
            }

            Some(PeerState::Disabled {
                open,
                connected_point,
                banned_until,
                ..
            }) => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Disconnected({:?}): Was disabled \
                     (through {:?})",
                    peer_id,
                    endpoint
                );
                let initiator = match connected_point {
                    ConnectedPoint::Dialer { .. } => true,
                    ConnectedPoint::Listener { .. } => false,
                };

                if let Some(until) = banned_until {
                    self.peers
                        .insert(peer_id.clone(), PeerState::Banned { until, initiator });
                }
                if open {
                    debug!(
                        target: crate::LOG_TARGET,
                        "External API <= Closed({:?})", peer_id
                    );
                    let event = CustomProtoOut::CustomProtocolClosed {
                        peer_id: peer_id.clone(),
                        endpoint: connected_point,
                        reason: "Disconnected by libp2p".into(),
                    };

                    self.events
                        .push(NetworkBehaviourAction::GenerateEvent(event));
                }
            }

            Some(PeerState::DisabledPendingEnable {
                open,
                connected_point,
                timer,
                ..
            }) => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Disconnected({:?}): Was disabled \
                     (through {:?}) but pending enable",
                    peer_id,
                    endpoint
                );
                let initiator = match connected_point {
                    ConnectedPoint::Dialer { .. } => true,
                    ConnectedPoint::Listener { .. } => false,
                };

                self.peers.insert(
                    peer_id.clone(),
                    PeerState::Banned {
                        until: timer.deadline(),
                        initiator,
                    },
                );
                if open {
                    debug!(
                        target: crate::LOG_TARGET,
                        "External API <= Closed({:?})", peer_id
                    );
                    let event = CustomProtoOut::CustomProtocolClosed {
                        peer_id: peer_id.clone(),
                        endpoint: connected_point,
                        reason: "Disconnected by libp2p".into(),
                    };

                    self.events
                        .push(NetworkBehaviourAction::GenerateEvent(event));
                }
            }

            Some(PeerState::Enabled {
                open,
                connected_point,
            }) => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Libp2p => Disconnected({:?}): Was enabled \
                     (through {:?})",
                    peer_id,
                    endpoint
                );

                if open {
                    debug!(
                        target: crate::LOG_TARGET,
                        "External API <= Closed({:?})", peer_id
                    );
                    let event = CustomProtoOut::CustomProtocolClosed {
                        peer_id: peer_id.clone(),
                        endpoint: connected_point,
                        reason: "Disconnected by libp2p".into(),
                    };

                    self.events
                        .push(NetworkBehaviourAction::GenerateEvent(event));
                }
            }

            Some(PeerState::Poisoned) => error!(
                target: crate::LOG_TARGET,
                "State of {:?} is poisoned", peer_id
            ),
        }
    }

    fn inject_addr_reach_failure(
        &mut self,
        peer_id: Option<&PeerId>,
        addr: &Multiaddr,
        error: &dyn error::Error,
    ) {
        trace!(
            target: crate::LOG_TARGET,
            "Libp2p => Reach failure for {:?} through {:?}: {:?}",
            peer_id,
            addr,
            error
        );
    }

    fn inject_dial_failure(&mut self, peer_id: &PeerId) {
        if let Entry::Occupied(mut entry) = self.peers.entry(peer_id.clone()) {
            match mem::replace(entry.get_mut(), PeerState::Poisoned) {
                // The node is not in our list.
                st @ PeerState::Banned { .. } => {
                    trace!(
                        target: crate::LOG_TARGET,
                        "Libp2p => Dial failure for {:?}",
                        peer_id
                    );
                    *entry.into_mut() = st;
                }

                // "Basic" situation: we failed to reach a node that was requested.
                PeerState::Requested | PeerState::PendingRequest { .. } => {
                    debug!(
                        target: crate::LOG_TARGET,
                        "Libp2p => Dial failure for {:?}", peer_id
                    );
                    *entry.into_mut() = PeerState::Banned {
                        until: self.clock.now() + Duration::from_secs(5),
                        initiator: true,
                    };
                }

                // We can still get dial failures even if we are already connected to the node,
                // as an extra diagnostic for an earlier attempt.
                st @ PeerState::Disabled { .. }
                | st @ PeerState::Enabled { .. }
                | st @ PeerState::DisabledPendingEnable { .. } => {
                    debug!(
                        target: crate::LOG_TARGET,
                        "Libp2p => Dial failure for {:?}", peer_id
                    );
                    *entry.into_mut() = st;
                }

                PeerState::Poisoned => error!(
                    target: crate::LOG_TARGET,
                    "State of {:?} is poisoned", peer_id
                ),
            }
        } else {
            // The node is not in our list.
            trace!(
                target: crate::LOG_TARGET,
                "Libp2p => Dial failure for {:?}",
                peer_id
            );
        }
    }

    fn inject_node_event(&mut self, source: PeerId, event: CustomProtoHandlerOut) {
        match event {
            CustomProtoHandlerOut::CustomProtocolClosed { reason } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) => Closed: {}", source, reason
                );

                let endpoint = match self.peer_endpoint(&source) {
                    Some(endpoint) => endpoint,
                    _ => {
                        error!(target: crate::LOG_TARGET, "Unable to read peer endpoint");
                        return;
                    }
                };

                let mut entry = if let Entry::Occupied(entry) = self.peers.entry(source.clone()) {
                    entry
                } else {
                    error!(
                        target: crate::LOG_TARGET,
                        "State mismatch in the custom protos handler"
                    );
                    return;
                };

                debug!(
                    target: crate::LOG_TARGET,
                    "External API <= Closed({:?})", source
                );
                let event = CustomProtoOut::CustomProtocolClosed {
                    peer_id: source.clone(),
                    endpoint,
                    reason,
                };
                self.events
                    .push(NetworkBehaviourAction::GenerateEvent(event));

                match mem::replace(entry.get_mut(), PeerState::Poisoned) {
                    PeerState::Enabled {
                        open,
                        connected_point,
                    } => {
                        debug_assert!(open);

                        debug!(
                            target: crate::LOG_TARGET,
                            "Handler({:?}) <= Disable", source
                        );
                        self.events.push(NetworkBehaviourAction::SendEvent {
                            peer_id: source.clone(),
                            event: CustomProtoHandlerIn::Disable,
                        });

                        *entry.into_mut() = PeerState::Disabled {
                            open: false,
                            connected_point,
                            banned_until: None,
                        };
                    }
                    PeerState::Disabled {
                        open,
                        connected_point,
                        banned_until,
                    } => {
                        debug_assert!(open);
                        *entry.into_mut() = PeerState::Disabled {
                            open: false,
                            connected_point,
                            banned_until,
                        };
                    }
                    PeerState::DisabledPendingEnable {
                        open,
                        connected_point,
                        timer,
                    } => {
                        debug_assert!(open);
                        *entry.into_mut() = PeerState::DisabledPendingEnable {
                            open: false,
                            connected_point,
                            timer,
                        };
                    }
                    _ => error!(
                        target: crate::LOG_TARGET,
                        "State mismatch in the custom protos handler"
                    ),
                }
            }

            CustomProtoHandlerOut::CustomProtocolOpen { version } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) => Open: version {:?}", source, version
                );
                let endpoint = match self.peers.get_mut(&source) {
                    Some(PeerState::Enabled {
                        ref mut open,
                        ref connected_point,
                    })
                    | Some(PeerState::DisabledPendingEnable {
                        ref mut open,
                        ref connected_point,
                        ..
                    })
                    | Some(PeerState::Disabled {
                        ref mut open,
                        ref connected_point,
                        ..
                    }) if !*open => {
                        *open = true;
                        connected_point.clone()
                    }
                    _ => {
                        error!(
                            target: crate::LOG_TARGET,
                            "State mismatch in the custom protos handler"
                        );
                        return;
                    }
                };

                debug!(
                    target: crate::LOG_TARGET,
                    "External API <= Open({:?})", source
                );
                let event = CustomProtoOut::CustomProtocolOpen {
                    version,
                    peer_id: source,
                    endpoint,
                };

                self.events
                    .push(NetworkBehaviourAction::GenerateEvent(event));
            }

            CustomProtoHandlerOut::CustomMessage { message } => {
                debug_assert!(self.is_open(&source));
                trace!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) => Message",
                    source
                );
                trace!(
                    target: crate::LOG_TARGET,
                    "External API <= Message({:?})",
                    source
                );

                let endpoint = match self.peer_endpoint(&source) {
                    Some(endpoint) => endpoint,
                    _ => {
                        error!(target: crate::LOG_TARGET, "Unable to read peer endpoint");
                        return;
                    }
                };

                let event = CustomProtoOut::CustomMessage {
                    peer_id: source,
                    endpoint,
                    message,
                };

                self.events
                    .push(NetworkBehaviourAction::GenerateEvent(event));
            }

            CustomProtoHandlerOut::Clogged { messages } => {
                debug_assert!(self.is_open(&source));
                trace!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) => Clogged",
                    source
                );
                trace!(
                    target: crate::LOG_TARGET,
                    "External API <= Clogged({:?})",
                    source
                );
                warn!(
                    target: crate::LOG_TARGET,
                    "Queue of packets to send to {:?} is \
                     pretty large",
                    source
                );
                self.events.push(NetworkBehaviourAction::GenerateEvent(
                    CustomProtoOut::Clogged {
                        peer_id: source,
                        messages,
                    },
                ));
            }

            // Don't do anything for non-severe errors except report them.
            CustomProtoHandlerOut::ProtocolError {
                is_severe,
                ref error,
            } if !is_severe => debug!(
                target: crate::LOG_TARGET,
                "Handler({:?}) => Benign protocol error: {:?}", source, error
            ),

            CustomProtoHandlerOut::ProtocolError { error, .. } => {
                debug!(
                    target: crate::LOG_TARGET,
                    "Handler({:?}) => Severe protocol error: {:?}", source, error
                );
                self.disconnect_peer_inner(&source, Some(Duration::from_secs(5)));
            }
        }
    }

    fn poll(
        &mut self,
        _params: &mut impl PollParameters,
    ) -> Async<NetworkBehaviourAction<CustomProtoHandlerIn, Self::OutEvent>> {
        for (peer_id, peer_state) in self.peers.iter_mut() {
            match mem::replace(peer_state, PeerState::Poisoned) {
                PeerState::PendingRequest { mut timer } => {
                    if let Ok(Async::NotReady) = timer.poll() {
                        *peer_state = PeerState::PendingRequest { timer };
                        continue;
                    }

                    debug!(
                        target: crate::LOG_TARGET,
                        "Libp2p <= Dial {:?} now that ban has expired", peer_id
                    );
                    self.events.push(NetworkBehaviourAction::DialPeer {
                        peer_id: peer_id.clone(),
                    });
                    *peer_state = PeerState::Requested;
                }

                PeerState::DisabledPendingEnable {
                    mut timer,
                    connected_point,
                    open,
                } => {
                    if let Ok(Async::NotReady) = timer.poll() {
                        *peer_state = PeerState::DisabledPendingEnable {
                            timer,
                            connected_point,
                            open,
                        };
                        continue;
                    }

                    debug!(
                        target: crate::LOG_TARGET,
                        "Handler({:?}) <= Enable now that ban has expired", peer_id
                    );
                    self.events.push(NetworkBehaviourAction::SendEvent {
                        peer_id: peer_id.clone(),
                        event: CustomProtoHandlerIn::Enable(connected_point.clone().into()),
                    });
                    *peer_state = PeerState::Enabled {
                        connected_point,
                        open,
                    };
                }

                st @ _ => *peer_state = st,
            }
        }

        if !self.events.is_empty() {
            return Async::Ready(self.events.remove(0));
        }

        Async::NotReady
    }
}
