use futures::Future;
use tokio::runtime::current_thread::Runtime;

pub fn create_runtime<F>(future: F) -> Runtime
where
    F: Future<Item = (), Error = ()> + Send + 'static,
{
    let mut runtime = Runtime::new().expect("failed to start new Runtime");
    runtime.spawn(future);
    runtime
}
