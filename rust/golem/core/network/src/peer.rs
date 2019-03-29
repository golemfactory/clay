use std::time;
use std::collections::HashMap;

use crate::message;

#[derive(Clone)]
pub struct ConnectedPeer {
	pub peer_info: PeerInfo
}

#[derive(Debug)]
pub struct Peer {
	pub info: PeerInfo,
	/// Requests we are no longer insterested in.
	obsolete_requests: HashMap<message::RequestId, time::Instant>,
	/// Request counter,
	next_request_id: message::RequestId,
}

#[derive(Clone, Debug)]
pub struct PeerInfo {
	pub protocol_version: u32,
}
