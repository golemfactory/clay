use env_logger::{Builder, WriteStyle};
use log::LevelFilter;

pub fn init() {
    Builder::from_default_env()
        .filter(None, LevelFilter::Info)
        .write_style(WriteStyle::Always)
        .init();
}
