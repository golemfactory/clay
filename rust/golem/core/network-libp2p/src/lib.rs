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

mod behaviour;
mod config;
mod custom_proto;
mod service;
mod transport;

pub use crate::config::*;
pub use crate::custom_proto::{CustomMessage, RegisteredProtocol};
pub use crate::config::{NetworkConfiguration, NodeKeyConfig, Secret, NonReservedPeerMode};
pub use crate::service::{start_service, Service, ServiceEvent};
pub use libp2p::{identity, multiaddr, build_multiaddr};
pub use libp2p::PeerId;
pub use libp2p::core::PublicKey;
pub use libp2p::core::nodes::ConnectedPoint;
pub use parity_multiaddr::{Multiaddr, Protocol as MultiaddrProtocol};

use serde::{Deserialize, Serialize};
use slog_derive::SerdeValue;
use std::{collections::{HashMap, HashSet}, error, fmt, time::Duration};

/// Protocol name
pub const PROTOCOL_NAME: &str = "golem";
/// Protocol version
pub const PROTOCOL_VERSION: &str = "1.0";
/// Log target name
pub const LOG_TARGET: &str = "golem-libp2p";

/// Protocol / handler id
pub type ProtocolId = [u8; 3];

/// Parses a string address and returns the component, if valid.
pub fn parse_str_addr(addr_str: &str) -> Result<(PeerId, Multiaddr), ParseErr> {
	let mut addr: Multiaddr = addr_str.parse()?;

	let who = match addr.pop() {
		Some(multiaddr::Protocol::P2p(key)) => PeerId::from_multihash(key)
			.map_err(|_| ParseErr::InvalidPeerId)?,
		_ => return Err(ParseErr::PeerIdMissing),
	};

	Ok((who, addr))
}

/// Error that can be generated by `parse_str_addr`.
#[derive(Debug)]
pub enum ParseErr {
	/// Error while parsing the multiaddress.
	MultiaddrParse(multiaddr::Error),
	/// Multihash of the peer ID is invalid.
	InvalidPeerId,
	/// The peer ID is missing from the address.
	PeerIdMissing,
}

impl fmt::Display for ParseErr {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            ParseErr::MultiaddrParse(err) => write!(f, "{}", err),
            ParseErr::InvalidPeerId => write!(f, "Peer id at the end of the address is invalid"),
            ParseErr::PeerIdMissing => write!(f, "Peer id is missing from the address"),
        }
    }
}

impl error::Error for ParseErr {
    fn source(&self) -> Option<&(dyn error::Error + 'static)> {
        match self {
            ParseErr::MultiaddrParse(err) => Some(err),
            ParseErr::InvalidPeerId => None,
            ParseErr::PeerIdMissing => None,
        }
    }
}

impl From<multiaddr::Error> for ParseErr {
	fn from(err: multiaddr::Error) -> ParseErr {
		ParseErr::MultiaddrParse(err)
	}
}

/// Returns general information about the networking.
///
/// Meant for general diagnostic purposes.
///
/// **Warning**: This API is not stable.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize, SerdeValue)]
#[serde(rename_all = "camelCase")]
pub struct NetworkState {
	/// PeerId of the local node.
	pub peer_id: String,
	/// List of addresses the node is currently listening on.
	pub listened_addresses: HashSet<Multiaddr>,
	/// List of addresses the node knows it can be reached as.
	pub external_addresses: HashSet<Multiaddr>,
	/// List of node we're connected to.
	pub connected_peers: HashMap<String, NetworkStatePeer>,
	/// List of node that we know of but that we're not connected to.
	pub not_connected_peers: HashMap<String, NetworkStateNotConnectedPeer>,
	/// Downloaded bytes per second averaged over the past few seconds.
	pub average_download_per_sec: u64,
	/// Uploaded bytes per second averaged over the past few seconds.
	pub average_upload_per_sec: u64,
	/// State of the peerset manager.
	pub peerset: serde_json::Value,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkStatePeer {
	/// How we are connected to the node.
	pub endpoint: NetworkStatePeerEndpoint,
	/// Node information, as provided by the node itself. Can be empty if not known yet.
	pub version_string: Option<String>,
	/// Latest ping duration with this node.
	pub latest_ping_time: Option<Duration>,
	/// If true, the peer is "enabled", which means that we try to open protocols
	/// with this peer. If false, we stick to Kademlia and/or other network-only protocols.
	pub enabled: bool,
	/// If true, the peer is "open", which means that we have an open protocol
	/// with this peer.
	pub open: bool,
	/// List of addresses known for this node.
	pub known_addresses: HashSet<Multiaddr>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct NetworkStateNotConnectedPeer {
	/// List of addresses known for this node.
	pub known_addresses: HashSet<Multiaddr>,
	/// Node information, as provided by the node itself, if we were ever connected to this node.
	pub version_string: Option<String>,
	/// Latest ping duration with this node, if we were ever connected to this node.
	pub latest_ping_time: Option<Duration>,
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub enum NetworkStatePeerEndpoint {
	/// We are dialing the given address.
	Dialing(Multiaddr),
	/// We are listening.
	Listening {
		/// Address we're listening on that received the connection.
		listen_addr: Multiaddr,
		/// Address data is sent back to.
		send_back_addr: Multiaddr,
	},
}

impl From<ConnectedPoint> for NetworkStatePeerEndpoint {
	fn from(endpoint: ConnectedPoint) -> Self {
		match endpoint {
			ConnectedPoint::Dialer { address } =>
				NetworkStatePeerEndpoint::Dialing(address),
			ConnectedPoint::Listener { listen_addr, send_back_addr } =>
				NetworkStatePeerEndpoint::Listening {
					listen_addr,
					send_back_addr
				}
		}
	}
}
