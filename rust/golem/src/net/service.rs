use std::convert;

use cpython::*;
use crossbeam_channel::Receiver;

use network::event::NetworkEvent;
use network::message::NetworkMessage;
use network::{
    identity, NetworkConfiguration, NetworkController, NetworkControllerPtr, NodeKeyConfig, Secret,
};

use crate::net::convert::*;
use crate::python::convert::*;
use crate::python::error::{Error, ErrorKind, ErrorSeverity};

impl convert::From<identity::error::DecodingError> for Error {
    fn from(e: identity::error::DecodingError) -> Self {
        Error::new(
            ErrorKind::Other,
            ErrorSeverity::High,
            format!("{:?}", e),
            None,
        )
    }
}

pub struct NetworkService {
    pub controller: Option<NetworkControllerPtr>,
    pub event_rx: Option<Receiver<NetworkEvent>>,
}

impl NetworkService {
    pub fn start(
        &mut self,
        py: Python,
        py_priv_key: PyBytes,
        py_host: PyString,
        py_port: PyLong,
    ) -> Result<(), Error> {
        if let Some(_) = self.controller {
            return Err(Error::already_running());
        }

        let priv_key = py_priv_key.data(py).to_vec();
        let priv_key = identity::secp256k1::SecretKey::from_bytes(priv_key)?;

        let address = to_socket_address(py, py_host, py_port)?;
        let multiaddr = sa_to_tcp_multiaddr(&address);

        let mut config = NetworkConfiguration::default();
        config.node_key = NodeKeyConfig::Secp256k1(Secret::Input(priv_key));
        config.listen_addresses = vec![multiaddr];

        let protocol_id: [u8; 3] = *b"fwd";
        let protocol_versions = &[1 as u8];

        let (controller, event_rx) =
            NetworkController::new(config, protocol_id, protocol_versions)?;

        self.controller = Some(controller);
        self.event_rx = Some(event_rx);

        Ok(())
    }

    pub fn stop(&self) -> Result<(), Error> {
        match self.controller {
            Some(ref service) => {
                service.lock().stop();
                Ok(())
            }
            None => Err(Error::not_running()),
        }
    }

    pub fn running(&self) -> bool {
        match self.controller {
            Some(_) => true,
            None => false,
        }
    }
}

impl NetworkService {
    pub fn connect(&self, py: Python, py_host: PyString, py_port: PyLong) -> Result<(), Error> {
        match self.controller {
            Some(ref controller) => {
                let address = to_socket_address(py, py_host, py_port)?;
                let multiaddr = sa_to_tcp_multiaddr(&address);

                controller.lock().connect(multiaddr);
                Ok(())
            }
            None => Err(Error::not_running()),
        }
    }

    pub fn connect_to_peer(&self, py: Python, py_peer_id: PyString) -> Result<(), Error> {
        match self.controller {
            Some(ref controller) => {
                let peer_id_string = py_extract!(py, py_peer_id)?;
                let peer_id = peer_id_from_str(&peer_id_string)?;

                controller.lock().connect_to_peer(peer_id);
                Ok(())
            }
            None => Err(Error::not_running()),
        }
    }

    pub fn disconnect(&self, py: Python, py_peer_id: PyString) -> Result<(), Error> {
        match self.controller {
            Some(ref controller) => {
                let peer_id_string = py_extract!(py, py_peer_id)?;
                let peer_id = peer_id_from_str(&peer_id_string)?;

                controller.lock().disconnect(peer_id);
                Ok(())
            }
            None => Err(Error::not_running()),
        }
    }

    pub fn send(&self, py: Python, py_peer_id: PyString, py_message: PyBytes) -> Result<(), Error> {
        match self.controller {
            Some(ref controller) => {
                let peer_id_string = py_extract!(py, py_peer_id)?;
                let peer_id = peer_id_from_str(&peer_id_string)?;
                let message = NetworkMessage::Blob(py_message.data(py).to_vec());

                controller.lock().send_message(peer_id, message);
                Ok(())
            }
            None => Err(Error::not_running()),
        }
    }
}
