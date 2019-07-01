use std::convert;
use std::io;
use std::net::SocketAddr;
use std::thread;

use cpython::*;
use crossbeam_channel::{self, Receiver};
use futures::sync::{mpsc, oneshot};
use futures::{future, Future, Sink};
use tokio;

use libp2p::identity;

use network_controller::event::NetworkEvent;
use network_controller::{
    ClientRequest, NetworkConfiguration, NetworkController, NodeKeyConfig, PeerId, Secret, UserMessage
};

use crate::net::runtime::create_runtime;
use crate::net::util::*;
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
    pub event_rx: Option<Receiver<NetworkEvent>>,
    request_tx: Option<mpsc::Sender<ClientRequest>>,
    shutdown_tx: Option<oneshot::Sender<()>>,
}

impl NetworkService {
    pub fn new() -> Self {
        NetworkService {
            event_rx: None,
            request_tx: None,
            shutdown_tx: None,
        }
    }

    pub fn start(
        &mut self,
        py: Python,
        py_priv_key: PyBytes,
        py_host: PyString,
        py_port: PyLong,
    ) -> Result<(), Error> {
        if let Some(_) = self.event_rx {
            return Err(Error::already_running());
        }

        let priv_key = py_priv_key.data(py).to_vec();
        let socket_addr = to_socket_address(py, py_host, py_port)?;
        let config = Self::build_config(priv_key, socket_addr)?;

        let (request_tx, request_rx) = mpsc::channel::<ClientRequest>(128);
        let (shutdown_tx, shutdown_rx) = oneshot::channel();
        let (spawn_tx, spawn_rx) = std::sync::mpsc::sync_channel(1);

        thread::spawn(move || {
            let (controller, event_rx) = match NetworkController::new(config) {
                Ok((controller, event_rx)) => (controller, event_rx),
                Err(e) => {
                    let _ = spawn_tx.send(Err(e));
                    return;
                }
            };

            let mut runtime = create_runtime(future::lazy(move || {
                tokio::spawn(
                    NetworkController::dispatch(controller.clone(), request_rx)
                        .select(shutdown_rx.then(|_| Ok(())))
                        .map(|(v, _)| v)
                        .map_err(|(e, _)| {
                            eprintln!("{:?}", e);
                        }),
                );

                Ok(())
            }));

            let _ = spawn_tx.send(Ok(event_rx));
            if let Err(e) = runtime.run() {
                eprintln!("Network runtime error: {:?}", e);
            }
        });

        match spawn_rx.recv()? {
            Ok(event_rx) => {
                self.event_rx = Some(event_rx);
                self.request_tx = Some(request_tx);
                self.shutdown_tx = Some(shutdown_tx);
                Ok(())
            }
            Err(e) => Err(e.into()),
        }
    }

    pub fn stop(&mut self) -> Result<(), Error> {
        if let Some(ref mut tx) = &mut self.request_tx {
            let _ = tx.start_send(ClientRequest::Stop);
        }

        if self.shutdown_tx.is_some() {
            let tx = self.shutdown_tx.take();
            if let Err(e) = tx.unwrap().send(()) {
                let err: io::Error = io::ErrorKind::BrokenPipe.into();
                return Err(err.into());
            }
        }

        Ok(())
    }

    #[inline]
    pub fn running(&self) -> bool {
        match self.event_rx {
            Some(_) => true,
            None => false,
        }
    }

    #[inline]
    fn assert_running(&self) -> Result<(), Error> {
        match self.event_rx {
            Some(_) => Ok(()),
            None => Err(Error::not_running()),
        }
    }

    fn build_config(
        priv_key: Vec<u8>,
        socket_addr: SocketAddr,
    ) -> Result<NetworkConfiguration, Error> {
        let priv_key = identity::secp256k1::SecretKey::from_bytes(priv_key)?;
        let priv_key = NodeKeyConfig::Secp256k1(Secret::Input(priv_key));
        let multiaddr = socket_addr.to_tcp_multiaddr();
        let mut config = NetworkConfiguration::default();

        config.node_key = priv_key;
        config.listen_addresses = vec![multiaddr];
        config.in_peers = 40;
        config.out_peers = 80;

        Ok(config)
    }

    #[inline]
    fn request(&mut self, request: ClientRequest) {
        let _ = self.request_tx.as_mut().unwrap().start_send(request);
    }
}

impl NetworkService {
    pub fn connect(&mut self, py: Python, py_host: PyString, py_port: PyLong) -> Result<(), Error> {
        self.assert_running()?;

        let address = to_socket_address(py, py_host, py_port)?;
        let multiaddr = address.to_tcp_multiaddr();

        self.request(ClientRequest::Connect(multiaddr));
        Ok(())
    }

    pub fn connect_to_peer(&mut self, py: Python, py_peer_id: PyString) -> Result<(), Error> {
        self.assert_running()?;

        let peer_id_string = py_extract!(py, py_peer_id)?;
        let peer_id = PeerId::from_string(&peer_id_string)?;

        self.request(ClientRequest::ConnectToPeer(peer_id));
        Ok(())
    }

    pub fn disconnect(&mut self, py: Python, py_peer_id: PyString, py_protocol_id: PyBytes) -> Result<(), Error> {
        self.assert_running()?;

        let peer_id_string = py_extract!(py, py_peer_id)?;
        let peer_id = PeerId::from_string(&peer_id_string)?;

        let mut protocol_id: [u8; 3] = [0, 0, 0];
        protocol_id.copy_from_slice(&py_protocol_id.data(py).to_vec()[0..3]);

        self.request(ClientRequest::DisconnectPeer(peer_id, protocol_id));
        Ok(())
    }

    pub fn send(
        &mut self,
        py: Python,
        py_peer_id: PyString,
        py_protocol_id: PyBytes,
        py_message: PyBytes,
    ) -> Result<(), Error> {
        self.assert_running()?;

        let peer_id_string = py_extract!(py, py_peer_id)?;
        let peer_id = PeerId::from_string(&peer_id_string)?;

        let mut protocol_id: [u8; 3] = [0, 0, 0];
        protocol_id.copy_from_slice(&py_protocol_id.data(py).to_vec()[0..3]);

        let message = UserMessage::Blob(protocol_id, py_message.data(py).to_vec());

        self.request(ClientRequest::SendMessage(peer_id, message));
        Ok(())
    }
}
