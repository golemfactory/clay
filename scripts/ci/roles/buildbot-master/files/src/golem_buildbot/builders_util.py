

def extract_rev(props):

    rev = props['revision'][0]
    if (rev is None or rev == "") and 'got_revision' in props:
        rev = props['got_revision'][0]

    return rev
