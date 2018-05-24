namespace py messages

struct Wrapper {
    1: string msg_name,
    2: binary msg_bytes,
    3: binary request_id
}
