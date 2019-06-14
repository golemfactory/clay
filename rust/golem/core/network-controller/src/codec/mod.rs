pub mod error;
pub mod serde;

pub trait Encoder {
    type Item;
    type Error;

    fn encode(&self, value: &Self::Item) -> Result<Vec<u8>, Self::Error>;
}

pub trait Decoder {
    type Item;
    type Error;

    fn decode(&self, value: &[u8]) -> Result<Option<Self::Item>, Self::Error>;
}
