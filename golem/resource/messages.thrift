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
    1: required string path,
    2: required string task_id,
    3: optional bool async_ = true,
    4: optional ClientOptions client_options
}

struct AddFiles {
    1: required list<string> files,
    2: required string task_id,
    3: optional string resource_hash,
    4: optional bool async_ = true,
    5: optional ClientOptions client_options
}

struct AddTask {
    1: required list<string> files,
    2: required string task_id,
    3: optional string resource_hash,
    4: optional bool async_ = true,
    5: optional ClientOptions client_options
}

struct RemoveTask {
    1: required string task_id
}

struct GetResources {
    1: required string task_id
}

struct PullResource {
    1: required ResourceEntry entry,
    2: required string task_id,
    3: optional ClientOptions client_options,
    4: optional bool async_ = true
}

/**
 * Responses
 */

struct Empty {

}

struct Error {
    1: optional string message
}

struct Added {
    1: required ResourceEntry entry
}

struct Resources {
    1: required list<Resource> resources
}

struct Pulled {
    1: required PulledEntry entry
}
