#![recursion_limit = "256"]
extern crate proc_macro;

use proc_macro::TokenStream;
use quote::quote;
use syn::parse_macro_input;
use syn::{Attribute, Data, DataStruct, DeriveInput, Field, Meta, NestedMeta};

const WORD_BEHAVIOUR: &str = "behaviour";
const WORD_IGNORE: &str = "ignore";

#[proc_macro_derive(DiscoveryNetBehaviour, attributes(behaviour))]
pub fn discovery_macro_derive(stream: TokenStream) -> TokenStream {
    let input = parse_macro_input!(stream as DeriveInput);
    match input.data {
        Data::Struct(ref data_struct) => discovery_macro_build(&input, data_struct),
        _ => {
            unimplemented!("Derive macro for DiscoveryNetBehaviour is only implemented for structs")
        }
    }
}

#[proc_macro_derive(PeerNetBehaviour, attributes(behaviour))]
pub fn peer_macro_derive(stream: TokenStream) -> TokenStream {
    let input = parse_macro_input!(stream as DeriveInput);
    match input.data {
        Data::Struct(ref data_struct) => peer_macro_build(&input, data_struct),
        _ => unimplemented!("Derive macro for PeerNetBehaviour is only implemented for structs"),
    }
}

fn discovery_macro_build(input: &DeriveInput, data_struct: &DataStruct) -> TokenStream {
    let trait_type = quote! {crate::DiscoveryNetBehaviour};
    let struct_name = &input.ident;
    let (_, type_generics, where_clause) = input.generics.split_for_impl();

    let generics = {
        let type_params = input.generics.type_params();
        let const_params = input.generics.const_params();
        let lifetimes = input.generics.lifetimes();

        quote! {<#(#lifetimes,)* #(#type_params,)* #(#const_params,)*>}
    };

    let statements = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        let statement = quote! {self.#field_name.add_discovered_nodes(nodes.iter().cloned());};
        Some(statement)
    });

    let output = quote! {
        impl #generics #trait_type for #struct_name #type_generics
        #where_clause
        {
            fn add_discovered_nodes(&mut self, nodes: impl Iterator<Item = PeerId>) {
                let nodes: Vec<PeerId> = nodes
                    .map(|p| p.clone())
                    .collect();

                #(#statements);*
            }
        }
    };

    output.into()
}

fn peer_macro_build(input: &DeriveInput, data_struct: &DataStruct) -> TokenStream {
    let trait_type = quote! {crate::PeerNetBehaviour};
    let struct_name = &input.ident;
    let (_, type_generics, where_clause) = input.generics.split_for_impl();

    let generics = {
        let type_params = input.generics.type_params();
        let const_params = input.generics.const_params();
        let lifetimes = input.generics.lifetimes();

        quote! {<#(#lifetimes,)* #(#type_params,)* #(#const_params,)*>}
    };

    let statement_ids = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        Some(quote! {protocol_ids.push(self.#field_name.id());})
    });

    let statement_open_peers = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        Some(quote! {peers.extend(self.#field_name.open_peers());})
    });

    let statement_is_open = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        Some(quote! {result &= self.#field_name.is_open(peer_id);})
    });

    let statement_is_enabled = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        Some(quote! {result &= self.#field_name.is_enabled(peer_id);})
    });

    let statement_connect = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        Some(quote! {self.#field_name.connect(multiaddr);})
    });

    let statement_connect_to_peer = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        Some(quote! {self.#field_name.connect_to_peer(peer_id);})
    });

    let statement_disconnect_peer = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        let mut stream = proc_macro2::TokenStream::new();

        stream.extend(quote! {
            if *protocol_id == self.#field_name.id() {
                self.#field_name.disconnect_peer(peer_id, protocol_id);
                return;
            }
        });

        Some(stream)
    });

    let statement_send_message = enumerate_fields(data_struct, move |(n, field)| {
        let field_name = field_name(n, field);
        let mut stream = proc_macro2::TokenStream::new();

        stream.extend(quote! {
            if *protocol_id == self.#field_name.id() {
                self.#field_name.send_message(peer_id, protocol_id, message);
                return;
            }
        });

        Some(stream)
    });

    let output = quote! {
        impl #generics #trait_type for #struct_name #type_generics
        #where_clause
        {
            fn protocol_ids(&self) -> Vec<ProtocolId> {
                let mut protocol_ids = Vec::new();
                #(#statement_ids);*
                protocol_ids
            }

            fn open_peers(&self) -> HashSet<PeerId> {
                let mut peers: HashSet<PeerId> = HashSet::new();
                #(#statement_open_peers);*
                peers
            }

            fn is_open(&self, peer_id: &PeerId) -> bool {
                let mut result = true;
                #(#statement_is_open);*
                result
            }

            fn is_enabled(&self, peer_id: &PeerId) -> bool {
                let mut result = true;
                #(#statement_is_enabled);*
                result
            }

            fn connect(&mut self, multiaddr: &Multiaddr) {
                #(#statement_connect);*
            }

            fn connect_to_peer(&mut self, peer_id: &PeerId) {
                #(#statement_connect_to_peer);*
            }

            fn disconnect_peer(&mut self, peer_id: &PeerId, protocol_id: &ProtocolId) {
                #(#statement_disconnect_peer);*
            }

            fn send_message(
                &mut self,
                peer_id: &PeerId,
                protocol_id: &ProtocolId,
                message: ProtocolMessage,
            ) {
                #(#statement_send_message);*

                error!("Cannot send a message: unknown protocol: {:?}", protocol_id);
            }
        }
    };

    output.into()
}

#[inline]
fn field_name(n: usize, field: &Field) -> proc_macro2::TokenStream {
    match field.ident {
        Some(ref i) => quote! {#i},
        None => quote! {#n},
    }
}

fn enumerate_fields<'d, F>(
    data_struct: &'d DataStruct,
    func: F,
) -> impl Iterator<Item = proc_macro2::TokenStream> + 'd
where
    F: FnMut((usize, &'d Field)) -> Option<proc_macro2::TokenStream> + 'd,
{
    data_struct
        .fields
        .iter()
        .filter(|f| !is_field_ignored(f))
        .enumerate()
        .filter_map(func)
}

fn is_field_ignored(field: &Field) -> bool {
    let meta_items_iter = field.attrs.iter().filter_map(nested_meta);

    for meta_vec in meta_items_iter {
        for meta_entry in meta_vec {
            match meta_entry {
                NestedMeta::Meta(Meta::Word(ref word)) if word == WORD_IGNORE => return true,
                _ => (),
            }
        }
    }

    false
}

fn nested_meta(attr: &Attribute) -> Option<Vec<NestedMeta>> {
    if attr.path.segments.len() != 1 || attr.path.segments[0].ident != WORD_BEHAVIOUR {
        return None;
    }

    match attr.interpret_meta() {
        Some(Meta::List(ref meta)) => {
            let nested = meta.nested.iter().cloned().collect();
            Some(nested)
        }
        _ => None,
    }
}
