namespace py messages

/**
 * Types
 */

union AddressEntry {
    1: string host,
    2: i32 port
}

struct ProtocolEntry {
    1: required list<AddressEntry> entries
}

struct PeerEntry {
    1: required map<string, ProtocolEntry> entries
}

union OptionValue {
    1: double timeout,
    2: list<PeerEntry> peers
}

struct ClientOptions {
    1: required string client_id,
    2: required string version,
    3: optional map<string, OptionValue> options
}

struct Resource {
    1: required string resource_hash,
    2: optional string task_id,
    3: optional list<string> files,
    4: optional string path
}

struct ResourceEntry {
    1: required string resource_hash,
    2: required list<string> files
}

/**
 * Requests
 */

struct AddFile {
    1: required binary request_id,
    2: required string path,
    3: required string task_id,
    4: optional string resource_hash,
    5: optional bool async_,
    6: optional ClientOptions client_options
}

struct AddFiles {
    1: required binary request_id,
    2: required list<string> files,
    3: required string task_id,
    4: optional string resource_hash,
    5: optional bool async_,
    6: optional ClientOptions client_options
}

struct AddTask {
    1: required binary request_id,
    2: required list<string> files,
    3: required string task_id,
    4: optional string resource_hash,
    5: optional bool async_,
    6: optional ClientOptions client_options
}

struct RemoveTask {
    1: required binary request_id,
    2: required string task_id
}

struct GetResources {
    1: required binary request_id,
    2: required string task_id
}

struct PullResource {
    1: required binary request_id,
    2: required ResourceEntry entry,
    3: required string task_id,
    4: optional ClientOptions client_options,
    5: optional bool async_
}

/**
 * Responses
 */

struct Error {
    1: required binary request_id,
    2: optional string message
}

struct Response {
    1: required binary request_id
}

struct Resources {
    1: required binary request_id,
    2: required list<Resource> resources
}
