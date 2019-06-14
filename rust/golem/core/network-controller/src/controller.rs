use std::io;
use std::sync::Arc;

use crossbeam_channel::{self, Receiver, Sender};
use futures::sync::mpsc;
use futures::{stream, Future, Stream};
use log::{debug, info, trace, warn};
use parking_lot::Mutex;

use network_libp2p::behaviour::Behaviour;
use network_libp2p::{multiaddr, NetworkBehaviour};
use network_libp2p::{start_service, CustomProto, LOG_TARGET};
use network_libp2p::{
    ConnectedPoint, NetworkConfiguration, PeerId, ProtocolId, PublicKey, StreamMuxerBox, Substream,
};
use network_libp2p::{Service as InternalService, ServiceEvent as InternalServiceEvent};

use crate::error::Error;
use crate::event::NetworkEvent;
use crate::message::UserMessage;
use crate::ClientRequest;

pub struct NetworkController {
    network_service: Arc<Mutex<InternalService>>,
    listen_addresses: Vec<multiaddr::Multiaddr>,
    event_tx: Sender<NetworkEvent>,
    shutting_down: bool,
}

impl Drop for NetworkController {
    fn drop(&mut self) {
        self.stop()
    }
}

impl NetworkController {
    pub fn new(
        config: NetworkConfiguration,
    ) -> Result<(Arc<Mutex<NetworkController>>, Receiver<NetworkEvent>), Error> {
        let (service, addrs) = match start_service(config) {
            Ok((service, addrs)) => {
                info!(target: LOG_TARGET, "Network service started: {:?}", addrs);
                (Arc::new(Mutex::new(service)), addrs)
            }
            Err(err) => {
                warn!(target: LOG_TARGET, "Network service error: {}", err);
                return Err(err.into());
            }
        };

        let (event_tx, event_rx) = crossbeam_channel::unbounded::<NetworkEvent>();
        let controller = Arc::new(Mutex::new(NetworkController {
            network_service: service.clone(),
            listen_addresses: addrs,
            event_tx,
            shutting_down: false,
        }));

        Ok((controller, event_rx))
    }

    #[inline]
    pub fn connect(&self, address: multiaddr::Multiaddr) {
        self.network_service.lock().connect(&address);
    }

    #[inline]
    pub fn connect_to_peer(&self, peer_id: PeerId) {
        self.network_service.lock().connect_to_peer(&peer_id);
    }

    #[inline]
    pub fn disconnect_peer(&self, peer_id: PeerId) {
        self.network_service.lock().disconnect_from_peer(&peer_id);
    }

    #[inline]
    pub fn send_message(&self, peer_id: PeerId, message: UserMessage) {
        let protocol_id = match message {
            UserMessage::Blob(protcol_id, _) => protcol_id,
        };

        self.network_service
            .lock()
            .send_message(&protocol_id, &peer_id, message.into());
    }

    #[inline]
    pub fn stop(&mut self) {
        self.shutting_down = true;
        let _ = self.event_tx.send(NetworkEvent::Terminated);
    }
}

impl NetworkController {
    fn on_peer_connected(
        &mut self,
        peer_id: PeerId,
        peer_pubkey: PublicKey,
        connected_point: ConnectedPoint,
    ) {
        debug!(
            target: LOG_TARGET,
            "Connected {:?} {}", connected_point, peer_id
        );

        let event = NetworkEvent::Connected(peer_id, connected_point, peer_pubkey);
        let _ = self.event_tx.send(event);
    }

    fn on_peer_disconnected(&mut self, peer_id: PeerId, connected_point: ConnectedPoint) {
        debug!(
            target: LOG_TARGET,
            "Disconnected {:?} {}", connected_point, peer_id
        );

        let event = NetworkEvent::Disconnected(peer_id, connected_point);
        let _ = self.event_tx.send(event);
    }

    fn on_peer_clogged(&self, peer_id: PeerId, msg: Option<UserMessage>) {
        debug!(target: LOG_TARGET, "Clogged: {} {:?}", peer_id, msg);

        let event = NetworkEvent::Clogged(peer_id, msg);
        let _ = self.event_tx.send(event);
    }

    fn on_message(
        &mut self,
        peer_id: PeerId,
        connected_point: ConnectedPoint,
        message: UserMessage,
    ) {
        trace!(target: LOG_TARGET, "Message: {} {:?}", peer_id, message);

        let event = NetworkEvent::Message(peer_id, connected_point, message);
        let _ = self.event_tx.send(event);
    }
}

impl NetworkController {
    #[inline]
    pub fn dispatch(
        controller: Arc<Mutex<NetworkController>>,
        request_rx: mpsc::Receiver<ClientRequest>,
    ) -> impl Future<Item = (), Error = io::Error> {
        let requests = Self::dispatch_requests(controller.clone(), request_rx);
        let events = Self::dispatch_events(controller);

        let futures: Vec<Box<Future<Item = (), Error = io::Error> + Send>> =
            vec![Box::new(requests) as Box<_>, Box::new(events) as Box<_>];

        futures::select_all(futures)
            .and_then(|_| Ok(()))
            .map_err(|(e, _, _)| e)
    }

    #[inline]
    pub fn dispatch_requests(
        controller: Arc<Mutex<NetworkController>>,
        request_rx: mpsc::Receiver<ClientRequest>,
    ) -> impl Future<Item = (), Error = io::Error> {
        let inner = controller.clone();

        request_rx
            .for_each(move |event| {
                match event {
                    ClientRequest::Connect(multiaddr) => inner.lock().connect(multiaddr),
                    ClientRequest::ConnectToPeer(peer_id) => inner.lock().connect_to_peer(peer_id),
                    ClientRequest::DisconnectPeer(peer_id) => inner.lock().disconnect_peer(peer_id),
                    ClientRequest::SendMessage(peer_id, message) => {
                        inner.lock().send_message(peer_id, message)
                    }
                    ClientRequest::Stop => {
                        inner.lock().stop();
                        return Err(());
                    }
                };

                Ok(())
            })
            .map_err(|_| io::Error::from(io::ErrorKind::Interrupted))
    }

    #[inline]
    pub fn dispatch_events(
        controller: Arc<Mutex<NetworkController>>,
    ) -> impl Future<Item = (), Error = io::Error> {
        let service = controller.lock().network_service.clone();
        let addresses = controller.lock().listen_addresses.clone();
        let _ = controller
            .lock()
            .event_tx
            .send(NetworkEvent::Listening(addresses));

        stream::poll_fn(move || service.lock().poll()).for_each(move |event| {
            match event {
                InternalServiceEvent::OpenedCustomProtocol {
                    peer_id,
                    peer_pubkey,
                    endpoint,
                    ..
                } => {
                    controller
                        .lock()
                        .on_peer_connected(peer_id, peer_pubkey, endpoint);
                }
                InternalServiceEvent::ClosedCustomProtocol {
                    peer_id, endpoint, ..
                } => {
                    controller.lock().on_peer_disconnected(peer_id, endpoint);
                }
                InternalServiceEvent::CustomMessage {
                    peer_id,
                    endpoint,
                    message,
                    ..
                } => {
                    let message = UserMessage::from(message);
                    controller.lock().on_message(peer_id, endpoint, message);
                }
                InternalServiceEvent::Clogged {
                    peer_id, messages, ..
                } => {
                    for msg in messages.into_iter().take(5) {
                        controller
                            .lock()
                            .on_peer_clogged(peer_id.clone(), Some(msg.into()));
                    }
                }
            };

            Ok(())
        })
    }
}
