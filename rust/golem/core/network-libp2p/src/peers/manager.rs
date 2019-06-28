use crate::{PeerId, PublicKey};
use std::collections::HashMap;

/// PeerManager placeholder struct. Its only purpose for now is to store peer keys.
#[derive(Debug)]
pub struct PeerManager {
    keystore: HashMap<PeerId, PublicKey>,
}

impl PeerManager {
    pub fn new() -> Self {
        PeerManager {
            keystore: HashMap::new(),
        }
    }
}

impl PeerManager {
    pub fn get_key(&self, peer_id: &PeerId) -> Option<PublicKey> {
        match self.keystore.get(peer_id) {
            Some(public_key) => Some(public_key.clone()),
            None => None,
        }
    }

    pub fn add_key(&mut self, peer_id: &PeerId, public_key: &PublicKey) {
        self.keystore.insert(peer_id.clone(), public_key.clone());
    }
}

impl PeerManager {
    // Placeholder method
    pub fn allowed(&mut self, _: &PeerId) -> bool {
        true
    }
}
