use cpython::{PyBytes, PyInt, PyTuple, Python, ToPyObject};

use network_controller::event::NetworkEvent;
use network_controller::{ConnectedPoint, UserMessage};

use crate::net::util::{MultiaddrConv, PublicKeyConv};

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
                        .filter_map(|ref address| address.to_host_port())
                        .collect();

                    py_wrap!(py, (EventId::Listening, addresses))
                }
                NetworkEvent::Terminated => py_wrap!(py, (EventId::Terminated,)),
                NetworkEvent::Connected(peer_id, connected_point, peer_pubkey) => {
                    let pubkey_bytes = peer_pubkey.to_bytes();
                    let py_pubkey = PyBytes::new(py, &pubkey_bytes[..]);

                    py_wrap!(
                        py,
                        (
                            EventId::Connected,
                            peer_id.to_string(),
                            connected_point_to_tuple(connected_point),
                            py_pubkey,
                        )
                    )
                }
                NetworkEvent::Disconnected(peer_id, connected_point) => py_wrap!(
                    py,
                    (
                        EventId::Disconnected,
                        peer_id.to_string(),
                        connected_point_to_tuple(connected_point),
                    )
                ),
                NetworkEvent::Message(peer_id, connected_point, message) => {
                    let message_tuple = match message {
                        UserMessage::Blob(protocol_id, message) => {
                            let protocol_id = PyBytes::new(py, &protocol_id);
                            let message = PyBytes::new(py, &message);
                            (protocol_id, message)
                        }
                    };

                    py_wrap!(
                        py,
                        (
                            EventId::Message,
                            peer_id.to_string(),
                            connected_point_to_tuple(connected_point),
                            message_tuple
                        )
                    )
                }
                NetworkEvent::Clogged(peer_id, _) => {
                    py_wrap!(py, (EventId::Clogged, peer_id.to_string(),))
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
        ConnectedPoint::Dialer { address } => {
            (ConnectedPointId::Dialer, address.to_host_port(), None)
        }
        ConnectedPoint::Listener {
            listen_addr,
            send_back_addr,
        } => (
            ConnectedPointId::Listener,
            send_back_addr.to_host_port(),
            listen_addr.to_host_port(),
        ),
    }
}
