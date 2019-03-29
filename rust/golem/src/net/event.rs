use cpython::{PyBytes, PyInt, PyTuple, Python, ToPyObject};

use network::event::NetworkEvent;
use network::message::NetworkMessage;
use network::ConnectedPoint;

use crate::net::convert::{multiaddr_to_host_port, peer_id_to_str, pubkey_encode};

pub fn event_into(py: Python, event: NetworkEvent) -> PyTuple {
    EventWrapper::NetworkEvent(event).into_py_object(py)
}

macro_rules! impl_int_enum_to_py {
    ($type:ty) => {
        impl ToPyObject for $type {
            type ObjectType = PyInt;

            fn to_py_object(&self, py: Python) -> Self::ObjectType {
                let value = (*self).clone() as u32;
                py_wrap!(py, value)
            }
        }
    };
}

#[derive(Clone, Debug)]
pub enum ConnectedPointId {
    Dialer = 0,
    Listener = 1,
}

// TODO: propagate network error messages and timeouts
#[derive(Clone, Debug)]
pub enum EventId {
    Listening = 10,
    Terminated = 11,
    Connected = 100,
    Disconnected = 110,
    Message = 200,
    Clogged = 300,
}

impl_int_enum_to_py!(ConnectedPointId);
impl_int_enum_to_py!(EventId);

enum EventWrapper {
    NetworkEvent(NetworkEvent),
}

impl ToPyObject for EventWrapper {
    type ObjectType = PyTuple;

    fn to_py_object(&self, _: Python) -> Self::ObjectType {
        unimplemented!()
    }

    fn into_py_object(self, py: Python) -> Self::ObjectType {
        match self {
            EventWrapper::NetworkEvent(event) => match event {
                NetworkEvent::Listening(addresses) => {
                    let addresses: Vec<(String, u16)> = addresses
                        .into_iter()
                        .filter_map(|ref address| multiaddr_to_host_port(address))
                        .collect();

                    py_wrap!(py, (EventId::Listening, addresses))
                }
                NetworkEvent::Terminated => py_wrap!(py, (EventId::Terminated,)),
                NetworkEvent::Connected(peer_id, peer_pubkey, connected_point) => {
                    let py_pubkey = PyBytes::new(py, &pubkey_encode(peer_pubkey)[..]);
                    py_wrap!(
                        py,
                        (
                            EventId::Connected,
                            peer_id_to_str(peer_id),
                            py_pubkey,
                            connected_point_to_tuple(connected_point),
                        )
                    )
                },
                NetworkEvent::Disconnected(peer_id, connected_point) => py_wrap!(
                    py,
                    (
                        EventId::Disconnected,
                        peer_id_to_str(peer_id),
                        connected_point_to_tuple(connected_point),
                    )
                ),
                NetworkEvent::Message(peer_id, connected_point, message) => {
                    let peer_id = peer_id_to_str(peer_id);
                    let message = match message {
                        NetworkMessage::Blob(v) => PyBytes::new(py, &v[..]),
                    };

                    py_wrap!(
                        py,
                        (
                            EventId::Message,
                            peer_id,
                            connected_point_to_tuple(connected_point),
                            message
                        )
                    )
                }
                NetworkEvent::Clogged(peer_id, _) => {
                    py_wrap!(py, (EventId::Clogged, peer_id_to_str(peer_id),))
                }
            },
        }
    }
}

fn connected_point_to_tuple(
    connected_point: ConnectedPoint,
) -> (
    ConnectedPointId,
    Option<(String, u16)>,
    Option<(String, u16)>,
) {
    match connected_point {
        ConnectedPoint::Dialer { address } => (
            ConnectedPointId::Dialer,
            multiaddr_to_host_port(&address),
            None,
        ),
        ConnectedPoint::Listener {
            listen_addr,
            send_back_addr,
        } => (
            ConnectedPointId::Listener,
            multiaddr_to_host_port(&send_back_addr),
            multiaddr_to_host_port(&listen_addr),
        ),
    }
}
