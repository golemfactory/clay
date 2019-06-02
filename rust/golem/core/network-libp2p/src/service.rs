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

use std::fs;
use std::io;
use std::path::Path;
use std::sync::Arc;
use std::collections::HashMap;

use futures::{prelude::*, Stream};
use libp2p::{Multiaddr, core::swarm::NetworkBehaviour, PeerId};
use libp2p::core::{Swarm, nodes::Substream, transport::boxed::Boxed, muxing::StreamMuxerBox};
use libp2p::core::nodes::ConnectedPoint;
use log::{info, warn, error};
use parking_lot::Mutex;

use crate::{behaviour::Behaviour, transport, NetworkState, NetworkStatePeer, NetworkStateNotConnectedPeer, PublicKey};
use crate::custom_proto::{CustomProto, CustomProtoOut, CustomMessage, RegisteredProtocol};
use crate::{NetworkConfiguration, NonReservedPeerMode, parse_str_addr};

/// Starts the libp2p service.
///
/// Returns a stream that must be polled regularly in order for the networking to function.
pub fn start_service<TMessage>(
	config: NetworkConfiguration,
	registered_custom: RegisteredProtocol<TMessage>,
) -> Result<(Service<TMessage>, peerset::PeersetHandle, Vec<Multiaddr>), io::Error>
where TMessage: CustomMessage + Send + 'static {

	if let Some(ref path) = config.net_config_path {
		fs::create_dir_all(Path::new(path))?;
	}

	// Private and public keys configuration.
	let local_identity = config.node_key.clone().into_keypair()?;
	let local_public = local_identity.public();
	let local_peer_id = local_public.clone().into_peer_id();

	// List of multiaddresses that we know in the network.
	let mut known_addresses = Vec::new();
	let mut listen_addresses = Vec::new();
	let mut bootstrap_nodes = Vec::new();
	let mut reserved_nodes = Vec::new();

	let mut process_nodes = |src: &Vec<String>, dest: &mut Vec<PeerId>, tag: &str| {
		for node in src.iter() {
			match parse_str_addr(node) {
				Ok((peer_id, addr)) => {
					dest.push(peer_id.clone());
					known_addresses.push((peer_id, addr));
				},
				Err(_) => warn!(target: crate::LOG_TARGET, "Not a valid {} node address: {}", tag, node),
			}
		}
	};

	process_nodes(&config.boot_nodes, &mut bootstrap_nodes, "bootstrap");
	process_nodes(&config.reserved_nodes, &mut reserved_nodes, "reserved");

	// Build the peerset.
	let (peerset, peerset_handle) = peerset::Peerset::from_config(peerset::PeersetConfig {
		in_peers: config.in_peers,
		out_peers: config.out_peers,
		bootnodes: bootstrap_nodes,
		reserved_only: config.non_reserved_mode == NonReservedPeerMode::Deny,
		reserved_nodes,
	});

	// Build the swarm.
	let (mut swarm, bandwidth, keystore) = {
		let user_agent = format!("{} ({})", config.client_version, config.node_name);
		let proto = CustomProto::new(registered_custom, peerset);
		let behaviour = Behaviour::new(proto, user_agent, local_public, known_addresses, config.enable_mdns);
		let (transport, bandwidth, keystore) = transport::build_transport(
			local_identity,
			config.wasm_external_transport,
		);
		(Swarm::new(transport, behaviour, local_peer_id.clone()), bandwidth, keystore)
	};

	// Listen on multiaddresses.
	for addr in &config.listen_addresses {
		if let Err(err) = Swarm::listen_on(&mut swarm, addr.clone()) {
			warn!(target: crate::LOG_TARGET, "Can't listen on {}: {:?}", addr, err)
		} else {
			listen_addresses.push(addr.clone())
		}
	}
	if listen_addresses.len() == 0 {
        return Err(io::Error::from(io::ErrorKind::AddrNotAvailable).into());
    }

	// Add external addresses.
	for addr in &config.public_addresses {
		Swarm::add_external_address(&mut swarm, addr.clone());
	}

	info!(target: crate::LOG_TARGET, "Local node identity is: {}", local_peer_id.to_base58());

	let service = Service {
		swarm,
		keystore,
		bandwidth,
		injected_events: Vec::new(),
	};

	Ok((service, peerset_handle, listen_addresses))
}

/// Event produced by the service.
#[derive(Debug)]
pub enum ServiceEvent<TMessage> {
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
		/// Node debug info
		debug_info: String,
	},

	/// A custom protocol substream has been closed.
	ClosedCustomProtocol {
		/// Identity of the node.
		peer_id: PeerId,
		/// Connected endpoint
		endpoint: ConnectedPoint,
		/// Node debug info
		debug_info: String,
	},

	/// Receives a message on a custom protocol stream.
	CustomMessage {
		/// Identity of the node.
		peer_id: PeerId,
		/// Connected endpoint
		endpoint: ConnectedPoint,
		/// Message that has been received.
		message: TMessage,
	},

	/// The substream with a node is clogged. We should avoid sending data to it if possible.
	Clogged {
		/// Index of the node.
		peer_id: PeerId,
		/// Copy of the messages that are within the buffer, for further diagnostic.
		messages: Vec<TMessage>,
	},
}

/// Network service. Must be polled regularly in order for the networking to work.
pub struct Service<TMessage> where TMessage: CustomMessage {
	/// Stream of events of the swarm.
	swarm: Swarm<
		Boxed<(PeerId, StreamMuxerBox), io::Error>,
		Behaviour<CustomProto<TMessage, Substream<StreamMuxerBox>>, CustomProtoOut<TMessage>, Substream<StreamMuxerBox>>
	>,

	/// Remote peer key storage
	// TODO: Incorporate into NodeInfo
	keystore: Arc<Mutex<HashMap<PeerId, PublicKey>>>,

	/// Bandwidth logging system. Can be queried to know the average bandwidth consumed.
	bandwidth: Arc<transport::BandwidthSinks>,

	/// Events to produce on the Stream.
	injected_events: Vec<ServiceEvent<TMessage>>,
}

impl<TMessage> Service<TMessage>
where TMessage: CustomMessage + Send + 'static {
	/// Returns a struct containing tons of useful information about the network.
	pub fn state(&mut self) -> NetworkState {
		let open = self.swarm.user_protocol().open_peers().cloned().collect::<Vec<_>>();

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
					enabled: swarm.user_protocol().is_enabled(&peer_id),
					open: swarm.user_protocol().is_open(&peer_id),
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
			peerset: self.swarm.user_protocol_mut().peerset_debug_info(),
		}
	}

	/// Returns an iterator that produces the list of addresses we're listening on.
	#[inline]
	pub fn listeners(&self) -> impl Iterator<Item = &Multiaddr> {
		Swarm::listeners(&self.swarm)
	}

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

	/// Returns the peer id of the local node.
	pub fn peer_id(&self) -> &PeerId {
		Swarm::local_peer_id(&self.swarm)
	}

	/// Returns the list of all the peers we are connected to.
	pub fn connected_peers<'a>(&'a self) -> impl Iterator<Item = &'a PeerId> + 'a {
		self.swarm.user_protocol().open_peers()
	}

	/// Returns the way we are connected to a node. Returns `None` if we are not connected to it.
	pub fn node_endpoint(&self, peer_id: &PeerId) -> Option<&ConnectedPoint> {
		if self.swarm.user_protocol().is_open(peer_id) {
			self.swarm.node(peer_id).map(|n| n.endpoint())
		} else {
			None
		}
	}

	/// Returns the latest client version reported by a node. Can return `Some` even for nodes
	/// we're not connected to.
	pub fn node_client_version(&self, peer_id: &PeerId) -> Option<&str> {
		self.swarm.node(peer_id).and_then(|n| n.client_version())
	}

	/// Sends a message to a peer using the custom protocol.
	///
	/// Has no effect if the connection to the node has been closed, or if the node index is
	/// invalid.
	pub fn send_custom_message(
		&mut self,
		peer_id: &PeerId,
		message: TMessage
	) {
		self.swarm.user_protocol_mut().send_packet(peer_id, message);
	}

	/// Disconnects a peer.
	///
	/// This is asynchronous and will not immediately close the peer.
	/// Corresponding closing events will be generated once the closing actually happens.
	pub fn drop_node(&mut self, peer_id: &PeerId) {
		self.swarm.user_protocol_mut().disconnect_peer(peer_id);
	}

	/// Adds a hard-coded address for the given peer, that never expires.
	pub fn add_known_address(&mut self, peer_id: PeerId, addr: Multiaddr) {
		self.swarm.add_known_address(peer_id, addr)
	}

	/// Get debug info for a given peer.
	pub fn peer_debug_info(&self, who: &PeerId) -> String {
		if let Some(node) = self.swarm.node(who) {
			format!("{:?} {}", who, node.debug_info())
		} else {
			format!("{:?} (unknown)", who)
		}
	}

	/// Polls for what happened on the network.
	fn poll_swarm(&mut self) -> Poll<Option<ServiceEvent<TMessage>>, io::Error> {
		loop {
			match self.swarm.poll() {
				Ok(Async::Ready(Some(CustomProtoOut::CustomProtocolOpen { peer_id, version, endpoint }))) => {
					let debug_info = self.peer_debug_info(&peer_id);
					let peer_pubkey = match self.keystore.lock().get(&peer_id) {
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
						debug_info,
					})))
				}
				Ok(Async::Ready(Some(CustomProtoOut::CustomProtocolClosed { peer_id, endpoint, .. }))) => {
					let debug_info = self.peer_debug_info(&peer_id);
					break Ok(Async::Ready(Some(ServiceEvent::ClosedCustomProtocol {
						peer_id,
						endpoint,
						debug_info,
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

impl<TMessage> Stream for Service<TMessage> where TMessage: CustomMessage + Send + 'static {
	type Item = ServiceEvent<TMessage>;
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
