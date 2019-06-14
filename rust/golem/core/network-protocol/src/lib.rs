mod behaviour;
mod custom_proto;
mod message;
mod protocol;

pub use behaviour::*;
pub use custom_proto::*;
pub use message::SerializableMessage;
pub use protocol::Protocol;

/// Protocol name
pub const PROTOCOL_NAME: &str = "golem";
/// Protocol version
pub const PROTOCOL_VERSION: &str = "0.1.0";
/// Log target name
pub const LOG_TARGET: &str = "golem-libp2p";

/// Protocol / handler id
pub type ProtocolId = [u8; 3];
