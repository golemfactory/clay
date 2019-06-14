// Copyright 2018-2019 Parity Technologies (UK) Ltd.
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

use std::io;
use std::sync::Arc;

use futures::{prelude::*, Stream};
use libp2p::{Multiaddr, PeerId};
use libp2p::core::muxing::StreamMuxerBox;
use libp2p::core::nodes::{ConnectedPoint, Substream};
use libp2p::core::swarm::{NetworkBehaviour, Swarm};
use libp2p::core::transport::boxed::Boxed;

use log::{info, warn, error};
use parking_lot::Mutex;

use network_protocol::{PeerNetBehaviour, ProtocolMessage, ProtocolId, CustomProtoOut};

use crate::{transport, NetworkState, NetworkStatePeer, NetworkStateNotConnectedPeer, PublicKey, NetworkConfiguration};
use crate::behaviour::Behaviour;
use crate::peers::manager::PeerManager;



/// Starts the libp2p service.
///
/// Returns a stream that must be polled regularly in order for the networking to function.
pub fn start_service(
	config: NetworkConfiguration,
) -> Result<(Service, Vec<Multiaddr>), io::Error> {
	// Private and public keys configuration.
	let local_identity = config.node_key.clone().into_keypair()?;
	let local_public = local_identity.public();
	let local_peer_id = local_public.clone().into_peer_id();

	let user_agent = format!("{} ({})", config.client_version, config.node_name);
	let peer_manager = Arc::new(Mutex::new(PeerManager::new()));

	// Build the swarm.
	let (mut swarm, bandwidth) = {
		let behaviour = Behaviour::new(user_agent, local_public, config.enable_mdns);
		let (transport, bandwidth) = transport::build_transport(
			local_identity,
			Arc::clone(&peer_manager),
			config.wasm_external_transport,
		);
		let swarm = Swarm::new(transport, behaviour, local_peer_id.clone());
		(swarm, bandwidth)
	};

	// Listen on multiaddresses.
	let mut listen_addresses = Vec::<Multiaddr>::new();
	for addr in &config.listen_addresses {
		if let Err(err) = Swarm::listen_on(&mut swarm, addr.clone()) {
			warn!(target: crate::LOG_TARGET, "Can't listen on {}: {:?}", addr, err)
		} else {
			listen_addresses.push(addr.clone())
		}
	}
	if listen_addresses.is_empty() {
        return Err(io::Error::from(io::ErrorKind::AddrNotAvailable).into());
    }

	// Add external addresses.
	for addr in &config.public_addresses {
		Swarm::add_external_address(&mut swarm, addr.clone());
	}

	info!(target: crate::LOG_TARGET, "Local node identity is: {}", local_peer_id.to_base58());

	let service = Service {
		swarm,
		peer_manager,
		bandwidth,
		injected_events: Vec::new(),
	};

	Ok((service, listen_addresses))
}

/// Event produced by the service.
#[derive(Debug)]
pub enum ServiceEvent {
	/// A custom protocol substream has been opened with a node.
	OpenedCustomProtocol {
		/// Identity of the node.
		peer_id: PeerId,
		/// Node's public key
		peer_pubkey: PublicKey,
		/// Version of the protocol that was opened.
		version: u8,
		/// Connected endpoint
		endpoint: ConnectedPoint,
	},

	/// A custom protocol substream has been closed.
	ClosedCustomProtocol {
		/// Identity of the node.
		peer_id: PeerId,
		/// Connected endpoint
		endpoint: ConnectedPoint,
	},

	/// Receives a message on a custom protocol stream.
	CustomMessage {
		/// Identity of the node.
		peer_id: PeerId,
		/// Connected endpoint
		endpoint: ConnectedPoint,
		/// Message that has been received.
		message: ProtocolMessage,
	},

	/// The substream with a node is clogged. We should avoid sending data to it if possible.
	Clogged {
		/// Index of the node.
		peer_id: PeerId,
		/// Copy of the messages that are within the buffer, for further diagnostic.
		messages: Vec<ProtocolMessage>,
	},
}

/// Network service. Must be polled regularly in order for the networking to work.
pub struct Service {
	/// Stream of events of the swarm.
	swarm: Swarm<
		Boxed<(PeerId, StreamMuxerBox), io::Error>,
		Behaviour<Substream<StreamMuxerBox>>,
	>,
	/// Remote peer manager
	peer_manager: Arc<Mutex<PeerManager>>,
	/// Bandwidth logging system. Can be queried to know the average bandwidth consumed.
	bandwidth: Arc<transport::BandwidthSinks>,
	/// Events to produce on the Stream.
	injected_events: Vec<ServiceEvent>,
}

impl Service {
	/// Returns the peer id of the local node.
	pub fn peer_id(&self) -> &PeerId {
		Swarm::local_peer_id(&self.swarm)
	}

	/// Returns an iterator that produces the list of addresses we're listening on.
	#[inline]
	pub fn listeners(&self) -> impl Iterator<Item = &Multiaddr> {
		Swarm::listeners(&self.swarm)
	}

	#[inline]
	pub fn connect(&mut self, multiaddr: &Multiaddr) {
		self.swarm.connect(multiaddr);
	}

	#[inline]
	pub fn connect_to_peer(&mut self, peer_id: &PeerId) -> bool {
		let allowed = self.peer_manager.lock().allowed(peer_id);
		if allowed {
			self.swarm.connect_to_peer(peer_id);
		} else {
			warn!("Cannot connect to peer {:?}: peer blocked", peer_id);
		}

		allowed
	}

	/// Disconnects a peer.
	///
	/// This is asynchronous and will not immediately close the peer.
	/// Corresponding closing events will be generated once the closing actually happens.
	#[inline]
	pub fn disconnect_from_peer(&mut self, peer_id: &PeerId) {
		self.swarm.disconnect_peer(peer_id);
	}

	/// Sends a message to a peer using the custom protocol.
	///
	/// Has no effect if the connection to the node has been closed, or if the node index is
	/// invalid.
	#[inline]
	pub fn send_message(
		&mut self,
		protocol_id: &ProtocolId,
		peer_id: &PeerId,
		message: ProtocolMessage
	) {
		self.swarm.send_message(protocol_id, peer_id, message);
	}
}

impl Service {
	/// Returns the downloaded bytes per second averaged over the past few seconds.
	#[inline]
	pub fn average_download_per_sec(&self) -> u64 {
		self.bandwidth.average_download_per_sec()
	}

	/// Returns the uploaded bytes per second averaged over the past few seconds.
	#[inline]
	pub fn average_upload_per_sec(&self) -> u64 {
		self.bandwidth.average_upload_per_sec()
	}
}

impl Service {
	/// Returns a struct containing tons of useful information about the network.
	pub fn state(&mut self) -> NetworkState {
		let open = self.swarm.open_peers();

		let connected_peers = {
			let swarm = &mut self.swarm;
			open.iter().filter_map(move |peer_id| {
				let known_addresses = NetworkBehaviour::addresses_of_peer(&mut **swarm, peer_id)
					.into_iter().collect();

				let endpoint = if let Some(e) = swarm.node(peer_id).map(|i| i.endpoint()) {
					e.clone().into()
				} else {
					error!(target: crate::LOG_TARGET, "Found state inconsistency between custom protocol \
						and debug information about {:?}", peer_id);
					return None
				};

				Some((peer_id.to_base58(), NetworkStatePeer {
					endpoint,
					version_string: swarm.node(peer_id).and_then(|i| i.client_version().map(|s| s.to_owned())).clone(),
					latest_ping_time: swarm.node(peer_id).and_then(|i| i.latest_ping()),
					enabled: swarm.is_enabled(&peer_id),
					open: swarm.is_open(&peer_id),
					known_addresses,
				}))
			}).collect()
		};

		let not_connected_peers = {
			let swarm = &mut self.swarm;
			let list = swarm.known_peers().filter(|p| open.iter().all(|n| n != *p))
				.cloned().collect::<Vec<_>>();
			list.into_iter().map(move |peer_id| {
				(peer_id.to_base58(), NetworkStateNotConnectedPeer {
					version_string: swarm.node(&peer_id).and_then(|i| i.client_version().map(|s| s.to_owned())).clone(),
					latest_ping_time: swarm.node(&peer_id).and_then(|i| i.latest_ping()),
					known_addresses: NetworkBehaviour::addresses_of_peer(&mut **swarm, &peer_id)
						.into_iter().collect(),
				})
			}).collect()
		};

		NetworkState {
			peer_id: Swarm::local_peer_id(&self.swarm).to_base58(),
			listened_addresses: Swarm::listeners(&self.swarm).cloned().collect(),
			external_addresses: Swarm::external_addresses(&self.swarm).cloned().collect(),
			average_download_per_sec: self.bandwidth.average_download_per_sec(),
			average_upload_per_sec: self.bandwidth.average_upload_per_sec(),
			connected_peers,
			not_connected_peers,
		}
	}

	/// Polls for what happened on the network.
	fn poll_swarm(&mut self) -> Poll<Option<ServiceEvent>, io::Error> {
		loop {
			match self.swarm.poll() {
				Ok(Async::Ready(Some(CustomProtoOut::CustomProtocolOpen { peer_id, version, endpoint }))) => {
					let peer_pubkey = match self.peer_manager.lock().get_key(&peer_id) {
						Some(pk) => pk.clone(),
						None => {
							error!("Public key not found for peer: {:?}", peer_id);
							break Ok(Async::NotReady);
						}
					};

					break Ok(Async::Ready(Some(ServiceEvent::OpenedCustomProtocol {
						peer_id,
						peer_pubkey,
						version,
						endpoint,
					})))
				}
				Ok(Async::Ready(Some(CustomProtoOut::CustomProtocolClosed { peer_id, endpoint, .. }))) => {
					break Ok(Async::Ready(Some(ServiceEvent::ClosedCustomProtocol {
						peer_id,
						endpoint,
					})))
				}
				Ok(Async::Ready(Some(CustomProtoOut::CustomMessage { peer_id, endpoint, message }))) => {
					break Ok(Async::Ready(Some(ServiceEvent::CustomMessage {
						peer_id,
						endpoint,
						message,
					})))
				}
				Ok(Async::Ready(Some(CustomProtoOut::Clogged { peer_id, messages }))) => {
					break Ok(Async::Ready(Some(ServiceEvent::Clogged {
						peer_id,
						messages,
					})))
				}
				Ok(Async::NotReady) => break Ok(Async::NotReady),
				Ok(Async::Ready(None)) => unreachable!("The Swarm stream never ends"),
				Err(_) => unreachable!("The Swarm never errors"),
			}
		}
	}
}

impl Stream for Service {
	type Item = ServiceEvent;
	type Error = io::Error;

	fn poll(&mut self) -> Poll<Option<Self::Item>, Self::Error> {
		if !self.injected_events.is_empty() {
			return Ok(Async::Ready(Some(self.injected_events.remove(0))));
		}

		match self.poll_swarm()? {
			Async::Ready(value) => return Ok(Async::Ready(value)),
			Async::NotReady => (),
		}

		// The only way we reach this is if we went through all the `NotReady` paths above,
		// ensuring the current task is registered everywhere.
		Ok(Async::NotReady)
	}
}
