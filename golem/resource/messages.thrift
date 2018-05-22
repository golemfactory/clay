namespace py messages

/**
 * Types
 */

struct AddressEntry {
    1: string host,
    2: i32 port
}

struct PeerEntry {
    1: required map<string, AddressEntry> entries
}

union Option {
    1: double timeout,
    2: list<PeerEntry> peers
    3: i64 size
}

struct ClientOptions {
    1: required string client_id,
    2: required double version,
    3: optional list<Option> options
}

struct Resource {
    1: required string hash,
    2: optional string task_id,
    3: optional list<string> files,
    4: optional string path
}

struct ResourceEntry {
    1: required string resource_hash,
    2: optional list<string> files
}

struct PulledEntry {
    1: required ResourceEntry entry,
    2: required list<string> files,
    3: required string task_id
}

/**
 * Requests
 */

struct AddFile {
    1: required binary request_id,
    2: required string path,
    3: required string task_id,
    4: optional bool async_ = true,
    5: optional ClientOptions client_options
}

struct AddFiles {
    1: required binary request_id,
    2: required list<string> files,
    3: required string task_id,
    4: optional string resource_hash,
    5: optional bool async_ = true,
    6: optional ClientOptions client_options
}

struct AddTask {
    1: required binary request_id,
    2: required list<string> files,
    3: required string task_id,
    4: optional string resource_hash,
    5: optional bool async_ = true,
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
    5: optional bool async_ = true
}

/**
 * Responses
 */

struct Error {
    1: required binary request_id,
    2: optional string message
}

struct Empty {
    1: required binary request_id
}

struct Added {
    1: required binary request_id,
    2: required ResourceEntry entry
}

struct Resources {
    1: required binary request_id,
    2: required list<Resource> resources
}

struct Pulled {
    1: required binary request_id,
    2: required PulledEntry entry
}
