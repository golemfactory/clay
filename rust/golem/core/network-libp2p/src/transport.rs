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

use std::{io, usize};
use std::sync::Arc;
use std::time::Duration;

use futures::prelude::*;
use parking_lot::Mutex;

use libp2p::{ InboundUpgradeExt, OutboundUpgradeExt, PeerId, Transport };
use libp2p::{ mplex, identity, secio, yamux, tcp, dns, bandwidth, wasm_ext, websocket };
use libp2p::core;
use libp2p::core::muxing::StreamMuxerBox;
use libp2p::core::transport::OptionalTransport;
use libp2p::core::transport::boxed::Boxed;

pub use self::bandwidth::BandwidthSinks;
use crate::peers::manager::PeerManager;

/// Builds the transport that serves as a common ground for all connections.
///
/// Returns a `BandwidthSinks` object that allows querying the average bandwidth produced by all
/// the connections spawned with this transport.
pub fn build_transport(
	keypair: identity::Keypair,
	peer_manager: Arc<Mutex<PeerManager>>,
	transport: Option<wasm_ext::ExtTransport>,
) -> (
	Boxed<(PeerId, StreamMuxerBox), io::Error>,
	Arc<bandwidth::BandwidthSinks>,
) {
	let mut mplex_config = mplex::MplexConfig::new();
	mplex_config.max_buffer_len_behaviour(mplex::MaxBufferBehaviour::Block);
	mplex_config.max_buffer_len(usize::MAX);

	let transport = match transport {
		Some(t) => OptionalTransport::some(t),
		None => OptionalTransport::none(),
	};

	#[cfg(not(target_os = "unknown"))]
	let transport = {
		let tcp_trans = tcp::TcpConfig::new();
		let ws_trans = websocket::WsConfig::new(tcp_trans.clone())
			.or_transport(tcp_trans);
		let dns_trans = dns::DnsConfig::new(ws_trans);

		transport.or_transport(dns_trans)
	};

	let (transport, bandwidth) = bandwidth::BandwidthLogging::new(transport, Duration::from_secs(5));

	let transport = transport
		.with_upgrade(secio::SecioConfig::new(keypair))
		.and_then(move |out, endpoint| {
			let key = out.remote_key.clone();
			let peer_id = out.remote_key.into_peer_id();
			let peer_id2 = peer_id.clone();

			peer_manager.lock().add_key(&peer_id, &key);

			let upgrade = core::upgrade::SelectUpgrade::new(yamux::Config::default(), mplex_config)
				.map_inbound(move |muxer| (peer_id, muxer))
				.map_outbound(move |muxer| (peer_id2, muxer));

			core::upgrade::apply(out.stream, upgrade, endpoint)
				.map(|(id, muxer)| (id, StreamMuxerBox::new(muxer)))
		})
		.with_timeout(Duration::from_secs(20))
		.map_err(|err| io::Error::new(io::ErrorKind::Other, err))
		.boxed();

	(transport, bandwidth)
}
