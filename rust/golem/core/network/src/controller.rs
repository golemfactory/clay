// Copyright 2017-2019 Parity Technologies (UK) Ltd.
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


use std::{io, thread};
use std::collections::HashMap;
use std::sync::Arc;

use crossbeam_channel::{self as channel, Receiver, Sender};
use futures::{Future, Stream, stream, sync::oneshot};
use log::{warn, debug, error};
use parking_lot::{Mutex, RwLock};
use tokio::runtime::Builder as RuntimeBuilder;

pub use network_libp2p::{identity, multiaddr};
pub use network_libp2p::{ ConnectedPoint, NetworkConfiguration, NodeKeyConfig, PeerId, PublicKey, Secret};
use network_libp2p::{start_service, ProtocolId, RegisteredProtocol, Multiaddr, LOG_TARGET};
use network_libp2p::{Service as InternalService, ServiceEvent as InternalServiceEvent};

use peerset::Peerset;

use crate::error::Error;
use crate::event::NetworkEvent;
use crate::message::NetworkMessage;
use crate::peer::{ConnectedPeer, PeerInfo};
use crate::PROTOCOL_VERSION;

pub type NetworkControllerPtr = Arc<Mutex<NetworkController>>;

fn create_channel<M>() -> (Sender<M>, Receiver<M>) {
	channel::unbounded()
}

struct ThreadLink {
	pub handle: thread::JoinHandle<()>,
	pub close_tx: oneshot::Sender<()>,
}

/// Network service. Handles network IO and manages connectivity.
pub struct NetworkController {
	peerset: Arc<Peerset>,
	connected_peers: Arc<RwLock<HashMap<PeerId, ConnectedPeer>>>,
	network_service: Arc<Mutex<InternalService<NetworkMessage>>>,
	event_tx: Sender<NetworkEvent>,
	/// Sender for messages to the background service task, and handle for the background thread.
	/// Dropping the sender should close the task and the thread.
	/// This is an `Option` because we need to extract it in the destructor.
	thread: Option<ThreadLink>,
}

impl Drop for NetworkController {
	fn drop(&mut self) {
		self.stop()
	}
}

impl NetworkController {
	/// Creates and registers the protocol within the network service
	pub fn new(
		config: NetworkConfiguration,
		protocol_id: ProtocolId,
		protocol_versions: &[u8],
	) -> Result<(NetworkControllerPtr, Receiver<NetworkEvent>), Error> {

		let (event_tx, event_rx) = create_channel::<NetworkEvent>();
		let (service, peerset) = match start_service(config, RegisteredProtocol::new(protocol_id, protocol_versions)) {
			Ok((service, peerset)) => {
				debug!(target: LOG_TARGET, "Network service started");
				(Arc::new(Mutex::new(service)), peerset)
			},
			Err(err) => {
				warn!(target: LOG_TARGET, "Network service start error: {}", err);
				return Err(err.into())
			},
		};
		let addresses: Vec<_> = service.lock().state().listened_addresses
			.into_iter()
			.map(|ref m| m.clone())
			.collect();

		if addresses.len() == 0 {
			return Err(io::Error::from(io::ErrorKind::AddrNotAvailable).into());
		}

		let controller = Arc::new(Mutex::new(NetworkController {
			peerset,
			connected_peers: Arc::new(Default::default()),
			network_service: service.clone(),
			event_tx: event_tx.clone(),
			thread: None,
		}));

		let thread_link = start_dispatcher(
			controller.clone(),
			service.clone(),
		)?;

		controller.lock().thread = Some(thread_link);

		let _ = event_tx.send(NetworkEvent::Listening(addresses));
		Ok((controller, event_rx))
	}

	#[inline]
	pub fn peer_id(&self) -> PeerId {
		self.network_service.lock().peer_id().clone()
	}

	#[inline]
	pub fn average_download_per_sec(&self) -> u64 {
		self.network_service.lock().average_download_per_sec()
	}

	#[inline]
	pub fn average_upload_per_sec(&self) -> u64 {
		self.network_service.lock().average_upload_per_sec()
	}
}

impl NetworkController {
	#[inline]
	pub fn stop(&mut self) {
		if let Some(thread_link) = self.thread.take() {
			let _ = thread_link.close_tx.send(());
			match thread_link.handle.join() {
				Ok(_) => {
					let _ = self.event_tx.send(NetworkEvent::Terminated);
				},
				Err(e) => {
					error!(target: LOG_TARGET, "Error waiting on service thread: {:?}", e);
				}
			}
		}
	}

	#[inline]
	pub fn connect(&self, address: Multiaddr) {
		self.peerset.as_ref().dial_addr(address);
	}

	#[inline]
	pub fn connect_to_peer(&self, peer_id: PeerId) {
		self.peerset.as_ref().add_reserved_peer(peer_id);
	}

	#[inline]
	pub fn disconnect(&self, peer_id: PeerId) -> bool {
		self.peerset.as_ref().remove_reserved_peer(&peer_id)
	}

	#[inline]
	pub fn send_message(&self, peer_id: PeerId, message: NetworkMessage) {
		self.network_service.lock().send_custom_message(&peer_id, message);
	}
}

impl NetworkController {
	pub(self) fn on_peer_connected(&mut self, peer_id: PeerId, peer_pubkey: PublicKey, connected_point: ConnectedPoint, debug_info: String) {
		debug!(target: LOG_TARGET, "Connecting {}: {}", peer_id, debug_info);

		// FIXME: provide proper connected peer info
		let peer_info = PeerInfo { protocol_version: PROTOCOL_VERSION };
		self.connected_peers.write().insert(peer_id.clone(), ConnectedPeer { peer_info });

		let event = NetworkEvent::Connected(peer_id, peer_pubkey, connected_point);
		let _ = self.event_tx.send(event);
	}

	pub(self) fn on_peer_disconnected(&mut self, peer_id: PeerId, connected_point: ConnectedPoint, debug_info: String) {
		debug!(target: LOG_TARGET, "Disconnecting {}: {}", peer_id, debug_info);
		self.connected_peers.write().remove(&peer_id);

		let event = NetworkEvent::Disconnected(peer_id, connected_point);
		let _ = self.event_tx.send(event);
	}

	pub(self) fn on_peer_clogged(&self, peer_id: PeerId, msg: Option<NetworkMessage>) {
		debug!(target: LOG_TARGET, "Peer cannot process messages fast enough: {} {:?}", peer_id, msg);

		let event = NetworkEvent::Clogged(peer_id, msg);
		let _ = self.event_tx.send(event);
	}

	pub(self) fn on_message(&mut self, peer_id: PeerId, connected_point: ConnectedPoint, message: NetworkMessage) {
		let event = NetworkEvent::Message(peer_id, connected_point, message);
		let _ = self.event_tx.send(event);
	}
}

/// Starts the background thread that handles the networking.
#[inline]
fn start_dispatcher(
	service: Arc<Mutex<NetworkController>>,
	network_service: Arc<Mutex<InternalService<NetworkMessage>>>,
) -> Result<ThreadLink, Error> {

	let (close_tx, close_rx) = oneshot::channel();
	let mut runtime = RuntimeBuilder::new().name_prefix("libp2p-").build()?;

	let handle = thread::Builder::new()
		.name("dispatcher".to_string())
		.spawn(move || {
			let dispatcher = dispatch(service, network_service)
				.select(close_rx.then(|_| Ok(())))
				.map(|(val, _)| val)
				.map_err(|(err,_ )| err);

			// Note that we use `block_on` and not `block_on_all` because we want to kill the thread
			// instantly if `close_rx` receives something.
			match runtime.block_on(dispatcher) {
				Ok(()) => debug!(target: LOG_TARGET, "Network thread finished"),
				Err(err) => error!(target: LOG_TARGET, "Network thread error: {:?}", err),
			};
		})?;

	Ok(ThreadLink{ handle, close_tx })
}

/// Runs the background thread that handles the networking.
#[inline]
fn dispatch(
	service: Arc<Mutex<NetworkController>>,
	network_service: Arc<Mutex<InternalService<NetworkMessage>>>,
) -> impl Future<Item = (), Error = io::Error> {

	// Process network-libp2p service events
	let events = stream::poll_fn(move || network_service.lock().poll()).for_each(move |event| {
		match event {
			InternalServiceEvent::OpenedCustomProtocol { peer_id, peer_pubkey, version, endpoint, debug_info, .. } => {
				debug_assert_eq!(version, PROTOCOL_VERSION as u8);
				service.lock().on_peer_connected(peer_id, peer_pubkey, endpoint, debug_info);
			}
			InternalServiceEvent::ClosedCustomProtocol { peer_id, endpoint, debug_info, .. } => {
				service.lock().on_peer_disconnected(peer_id, endpoint, debug_info);
			}
			InternalServiceEvent::CustomMessage { peer_id, endpoint, message, .. } => {
				service.lock().on_message(peer_id, endpoint, message);
			}
			InternalServiceEvent::Clogged { peer_id, messages, .. } => {
				debug!(target: LOG_TARGET, "{} clogging messages:", messages.len());

				for msg in messages.into_iter().take(5) {
					service.lock().on_peer_clogged(peer_id.clone(), Some(msg));
				}
			}
		};

		Ok(())
	});

	let futures: Vec<Box<Future<Item = (), Error = io::Error> + Send>> = vec![
		Box::new(events) as Box<_>
	];

	futures::select_all(futures)
		.and_then(|_| Ok(()))
		.map_err(|(e, _, _)| e)
}
