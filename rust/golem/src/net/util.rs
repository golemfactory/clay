use std::net::{IpAddr, SocketAddr};
use std::str::FromStr;

use secp256k1;

use network_controller::multiaddr::{Error as MultiaddrError, Multiaddr, Protocol};
use network_controller::{identity, PeerId, PublicKey};

use crate::python::error::{Error, ErrorKind, ErrorSeverity};

pub trait MultiaddrConv {
    fn to_host_port(&self) -> Option<(String, u16)>;
    fn to_socket_addr(&self) -> Result<SocketAddr, MultiaddrError>;
}

pub trait SocketAddrConv {
    fn to_host_port(&self) -> (String, u16);
    fn to_tcp_multiaddr(&self) -> Multiaddr;
}

pub trait PeerIdConv {
    fn from_string(peer_id_string: &String) -> Result<PeerId, Error>;
}

pub trait PublicKeyConv {
    fn to_bytes(&self) -> Vec<u8>;
}

impl MultiaddrConv for Multiaddr {
    #[inline]
    fn to_host_port(&self) -> Option<(String, u16)> {
        match self.to_socket_addr() {
            Ok(socket_addr) => Some(socket_addr.to_host_port()),
            Err(e) => None,
        }
    }

    fn to_socket_addr(&self) -> Result<SocketAddr, MultiaddrError> {
        let invalid = || Err(MultiaddrError::InvalidMultiaddr);
        let mut iter = self.iter();

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
                Protocol::Dccp(port)
                | Protocol::Onion(_, port)
                | Protocol::Sctp(port)
                | Protocol::Tcp(port)
                | Protocol::Udp(port) => port,
                _ => return invalid(),
            },
            None => return invalid(),
        };

        Ok(SocketAddr::new(ip, port))
    }
}

impl SocketAddrConv for SocketAddr {
    #[inline]
    fn to_host_port(&self) -> (String, u16) {
        (self.ip().to_string(), self.port())
    }

    fn to_tcp_multiaddr(&self) -> Multiaddr {
        let mut multiaddr = Multiaddr::from(Protocol::from(self.ip()));
        multiaddr.push(Protocol::Tcp(self.port()));
        multiaddr
    }
}

impl PeerIdConv for PeerId {
    #[inline]
    fn from_string(peer_id_string: &String) -> Result<PeerId, Error> {
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
}

impl PublicKeyConv for PublicKey {
    fn to_bytes(&self) -> Vec<u8> {
        match self {
            PublicKey::Ed25519(key) => key.encode().to_vec(),
            #[cfg(not(any(target_os = "emscripten", target_os = "unknown")))]
            PublicKey::Rsa(key) => key.encode_pkcs1(),
            PublicKey::Secp256k1(key) => key.to_bytes(),
        }
    }
}

impl PublicKeyConv for identity::secp256k1::PublicKey {
    fn to_bytes(&self) -> Vec<u8> {
        // secp256k1_lib::PublicKey is private
        let encoded = self.encode();
        let deserialized = secp256k1::PublicKey::from_slice(&encoded).unwrap();
        // serialize_uncompressed returns a byte-prefixed 64 byte key
        deserialized.serialize_uncompressed()[1..].to_vec()
    }
}

impl From<MultiaddrError> for Error {
    fn from(e: MultiaddrError) -> Self {
        Error::new(
            ErrorKind::Other,
            ErrorSeverity::Medium,
            format!("{:?}", e),
            None,
        )
    }
}
