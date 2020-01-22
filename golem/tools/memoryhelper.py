def dir_size_to_display(dir_size):
    if dir_size // (1024 * 1024 * 1024) > 0:
        dir_size = round(float(dir_size) / (1024 * 1024 * 1024), 1)
        return f'{dir_size} GiB'
    if dir_size // (1024 * 1024) > 0:
        dir_size = round(float(dir_size) / (1024 * 1024), 1)
        return f'{dir_size} MiB'
    if dir_size // 1024 > 0:
        dir_size = round(float(dir_size) / 1024, 1)
        return f'{dir_size} KiB'
    return f'{dir_size} B'
