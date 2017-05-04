def find_wrong_renderer_warning(log_content):
    text = "error: engine"
    for l in log_content.splitlines():
        if l.lower().startswith(text):
            return l[len(text):]
    return ""

