use crate::{PeerId, PublicKey};
use std::collections::HashMap;
use std::ops::Add;
use std::time::{Instant, Duration};

#[derive(Clone, Debug)]
pub enum BlockedState {
    Timeout(Instant),
    Indefinite,
}

#[derive(Clone, Debug)]
pub enum PeerManagerRequest {
    Block(PeerId, Option<u64>),
    Unblock(PeerId),
}

/// A placeholder class for the PeerManager.
#[derive(Debug)]
pub struct PeerManager {
    keystore: HashMap<PeerId, PublicKey>,
    blocked: HashMap<PeerId, BlockedState>,
}

impl PeerManager {
    pub fn new() -> Self {
        PeerManager {
            keystore: HashMap::new(),
            blocked: HashMap::new(),
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

    pub fn remove_key(&mut self, peer_id: &PeerId) -> Option<PublicKey> {
        self.keystore.remove(peer_id)
    }
}

impl PeerManager {
    pub fn allowed(&mut self, peer_id: &PeerId) -> bool {
        match self.blocked.get(peer_id) {
            Some(state) => {
                match state {
                    BlockedState::Timeout(instant) => {
                        let expired = instant < &Instant::now();
                        if expired {
                            self.unblock(peer_id);
                        }

                        expired
                    },
                    BlockedState::Indefinite => false,
                }
            },
            None => true,
        }
    }

    pub fn block(&mut self, peer_id: PeerId, timeout_ms: Option<u64>) {
        match timeout_ms {
            Some(timeout_ms) => {
                let instant = Instant::now().add(Duration::from_millis(timeout_ms));
                let state = BlockedState::Timeout(instant);
                self.blocked.insert(peer_id, state);
            },
            None => {
                let state = BlockedState::Indefinite;
                self.blocked.insert(peer_id, state);
            }
        }
    }

    pub fn unblock(&mut self, peer_id: &PeerId) -> bool {
        match self.blocked.remove(peer_id) {
            Some(_) => true,
            None => false,
        }
    }
}
