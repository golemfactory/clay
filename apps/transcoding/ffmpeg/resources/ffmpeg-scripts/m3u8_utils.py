import os
import re
import m3u8

def create_and_dump_m3u8(path, segment):
    [basename, _] = os.path.splitext(segment.uri)
    [basename, _,num] = basename.rpartition('_')
    filename = os.path.join(path, basename + "[num=" + num + "]" + ".m3u8")
    file = open(filename, 'w')
    file.write("#EXTM3U\n")
    file.write("#EXT-X-VERSION:3\n")
    file.write("#EXT-X-TARGETDURATION:{}\n".format(segment.duration))
    file.write("#EXT-X-MEDIA-SEQUENCE:0\n")
    file.write("#EXTINF:{},\n".format(segment.duration))
    file.write("{}\n".format(segment.uri))
    file.write("#EXT-X-ENDLIST\n")
    file.close()
    return filename

def join_playlists(playlists_dir):
    playlists = get_playlists(playlists_dir)
    base = m3u8.load(playlists[0])
    for pl in playlists[1:]:
        playlist = m3u8.load(pl)
        for segment in playlist.segments:
            base.add_segment(segment)
    return base

def get_playlists(playlists_dir):
    playlists = [os.path.join(playlists_dir,f) for f in os.listdir(playlists_dir) if f.endswith('_TC.m3u8')]
    return sort_playlists(playlists)

def sort_playlists(playlists):
    playlists_dict = {} 
    regex = r'\[num=[0-9]+\]'
    for playlist in playlists:
        [_, num] = re.findall(regex, playlist)[0].split('=')
        num = num[:-1]
        playlists_dict[int(num)] = playlist
    return [value for key, value in sorted(playlists_dict.items())]