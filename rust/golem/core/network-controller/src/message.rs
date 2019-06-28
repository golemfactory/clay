use lazy_static::lazy_static;
use serde::{Deserialize, Serialize};

use network_libp2p::{ProtocolId, ProtocolMessage, SerializableMessage};

use crate::codec::serde::SerdeCodec;
use crate::codec::{Decoder, Encoder};

lazy_static! {
    static ref CODEC: SerdeCodec<UserMessage> = SerdeCodec::new();
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub enum UserMessage {
    Blob(ProtocolId, Vec<u8>),
}

unsafe impl Send for UserMessage {}
unsafe impl Sync for UserMessage {}

impl Into<ProtocolMessage> for UserMessage {
    fn into(self) -> ProtocolMessage {
        match self {
            UserMessage::Blob(protocol_id, bytes) => ProtocolMessage::Blob(protocol_id, bytes),
        }
    }
}

impl From<ProtocolMessage> for UserMessage {
    fn from(message: ProtocolMessage) -> Self {
        match message {
            ProtocolMessage::Blob(protocol_id, bytes) => UserMessage::Blob(protocol_id, bytes),
        }
    }
}

impl SerializableMessage for UserMessage {
    fn into_bytes(self) -> Vec<u8> {
        CODEC.encode(&self).unwrap()
    }

    fn from_bytes(bytes: &[u8]) -> Result<Self, ()>
    where
        Self: Sized,
    {
        match CODEC.decode(bytes) {
            Ok(m) => match m {
                Some(m) => Ok(m),
                None => Err(()),
            },
            Err(_) => Err(()),
        }
    }
}
