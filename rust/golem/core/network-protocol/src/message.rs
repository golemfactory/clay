pub trait SerializableMessage {
    fn into_bytes(self) -> Vec<u8>;

    fn from_bytes(bytes: &[u8]) -> Result<Self, ()>
    where
        Self: Sized;
}

impl SerializableMessage for Vec<u8> {
    fn into_bytes(self) -> Vec<u8> {
        self
    }

    fn from_bytes(bytes: &[u8]) -> Result<Self, ()> {
        Ok(bytes.to_vec())
    }
}
