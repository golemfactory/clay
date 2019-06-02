use std::io;
use std::net::{IpAddr, SocketAddr};
use std::str::FromStr;

use secp256k1;

use network::identity;
use network::{Multiaddr, MultiaddrProtocol as Protocol, PeerId, PublicKey};

use crate::python::error::{Error, ErrorKind, ErrorSeverity};

#[inline]
pub fn multiaddr_to_host_port(multiaddr: &Multiaddr) -> Option<(String, u16)> {
    match sa_from_tcp_multiaddr(multiaddr) {
        Ok(socket_addr) => Some(sa_to_host_port(&socket_addr)),
        Err(e) => None,
    }
}

#[inline]
pub fn sa_to_host_port(socket_addr: &SocketAddr) -> (String, u16) {
    (socket_addr.ip().to_string(), socket_addr.port())
}

pub fn sa_to_tcp_multiaddr(socket_addr: &SocketAddr) -> Multiaddr {
    let mut multiaddr = Multiaddr::from(Protocol::from(socket_addr.ip()));
    multiaddr.push(Protocol::Tcp(socket_addr.port()));
    multiaddr
}

pub fn sa_from_tcp_multiaddr(multiaddr: &Multiaddr) -> Result<SocketAddr, io::Error> {
    let invalid = || Err(io::Error::from(io::ErrorKind::InvalidInput));
    let mut iter = multiaddr.iter();

    let ip = match iter.next() {
        Some(protocol) => match protocol {
            Protocol::Ip4(ipv4) => IpAddr::from(ipv4),
            Protocol::Ip6(ipv6) => IpAddr::from(ipv6),
            _ => return invalid(),
        },
        None => return invalid(),
    };

    let port = match iter.next() {
        Some(protocol) => match protocol {
            Protocol::Tcp(port) => port,
            _ => return invalid(),
        },
        None => return invalid(),
    };

    Ok(SocketAddr::new(ip, port))
}

#[inline]
pub fn peer_id_to_str(peer_id: PeerId) -> String {
    peer_id.to_string()
}

#[inline]
pub fn peer_id_from_str(peer_id_string: &String) -> Result<PeerId, Error> {
    match PeerId::from_str(peer_id_string) {
        Ok(peer_id) => Ok(peer_id),
        Err(_) => Err(Error::new(
            ErrorKind::Other,
            ErrorSeverity::Low,
            "invalid peer id",
            None,
        )),
    }
}

pub trait PublicKeyToBytes {
    fn to_bytes(&self) -> Vec<u8>;
}

impl PublicKeyToBytes for PublicKey {
    fn to_bytes(&self) -> Vec<u8> {
        match self {
            PublicKey::Ed25519(key) => key.encode().to_vec(),
            #[cfg(not(any(target_os = "emscripten", target_os = "unknown")))]
            PublicKey::Rsa(key) => key.encode_pkcs1(),
            PublicKey::Secp256k1(key) => key.to_bytes(),
        }
    }
}

impl PublicKeyToBytes for identity::secp256k1::PublicKey {
    fn to_bytes(&self) -> Vec<u8> {
        // secp256k1_lib::PublicKey is private
        let encoded = self.encode();
        let deserialized = secp256k1::PublicKey::from_slice(&encoded).unwrap();
        // serialize_uncompressed returns a byte-prefixed 64 byte key
        deserialized.serialize_uncompressed()[1..].to_vec()
    }
}
