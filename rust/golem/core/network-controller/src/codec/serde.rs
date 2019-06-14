use std::marker::PhantomData;
use std::mem::size_of;

use bincode;
use byteorder::{BigEndian, ByteOrder};
use bytes::{BufMut, BytesMut};
use serde::{Deserialize, Serialize};
use tokio_codec;

use super::error;
use super::{Decoder, Encoder};

type LenType = u32;
const LEN_SZ: usize = size_of::<u32>();

pub struct SerdeCodec<M>
where
    M: for<'de> Deserialize<'de> + Serialize,
{
    config: bincode::Config,
    phantom: PhantomData<M>,
}

impl<M> SerdeCodec<M>
where
    M: for<'de> Deserialize<'de> + Serialize,
{
    pub fn new() -> Self {
        let mut config = bincode::config();
        config.big_endian();
        SerdeCodec {
            config,
            phantom: PhantomData,
        }
    }

    fn encode_impl(&self, item: &M, dst: &mut BytesMut) -> Result<(), error::CodecError> {
        let serialized = self.config.serialize::<M>(item)?;
        let as_ref: &[u8] = serialized.as_ref();
        dst.reserve(LEN_SZ + serialized.len());
        dst.put_u32_be(serialized.len() as LenType);
        dst.put(as_ref);
        Ok(())
    }

    fn decode_impl(&self, src: &mut BytesMut) -> Result<Option<M>, error::CodecError> {
        if src.len() < LEN_SZ {
            return Ok(None);
        }

        let size = BigEndian::read_u32(src.as_ref()) as usize;
        if src.len() < size + LEN_SZ {
            return Ok(None);
        }

        src.split_to(LEN_SZ);

        let item = src.split_to(size);
        let item = self.config.deserialize::<M>(item.as_ref())?;

        Ok(Some(item))
    }
}

impl<M> Encoder for SerdeCodec<M>
where
    M: for<'de> Deserialize<'de> + Serialize,
{
    type Item = M;
    type Error = error::CodecError;

    fn encode(&self, value: &Self::Item) -> Result<Vec<u8>, Self::Error> {
        let mut bytes = BytesMut::new();
        self.encode_impl(value, &mut bytes)?;
        Ok(bytes.to_vec())
    }
}

impl<M> Decoder for SerdeCodec<M>
where
    M: for<'de> Deserialize<'de> + Serialize,
{
    type Item = M;
    type Error = error::CodecError;

    fn decode(&self, value: &[u8]) -> Result<Option<M>, Self::Error> {
        let mut bytes = BytesMut::from(value);
        self.decode_impl(&mut bytes)
    }
}

impl<M> tokio_codec::Encoder for SerdeCodec<M>
where
    M: for<'de> Deserialize<'de> + Serialize,
{
    type Item = M;
    type Error = error::CodecError;

    fn encode(&mut self, item: Self::Item, dst: &mut BytesMut) -> Result<(), Self::Error> {
        self.encode_impl(&item, dst)
    }
}

impl<M> tokio_codec::Decoder for SerdeCodec<M>
where
    M: for<'de> Deserialize<'de> + Serialize,
{
    type Item = M;
    type Error = error::CodecError;

    fn decode(&mut self, src: &mut BytesMut) -> Result<Option<Self::Item>, Self::Error> {
        self.decode_impl(src)
    }
}
