from fireworks.utilities.filepad import FilePad

fp = FilePad.auto_load()
file_id, label = fp.get_file('result')
print(file_id)
