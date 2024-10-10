import diskcache
import json
import os

dest_dir = "/home/chris/Jungle/photoboxy"
db = diskcache.Index(dest_dir+'/.db')
face_indexer = db['.cluster_cache']

names_file = dest_dir+'/faces/names.json'
with open(names_file, 'r') as fh:
    mappings = json.load(fh)

missed = 0
skipped = 0
mapped = 0
for face_id, name in mappings.items():
    if name.isnumeric():
        skipped += 1
        continue
    face_id = int(face_id)
    if face_id not in face_indexer.names:
        missed += 1
        continue
    if not face_indexer.names[face_id].isnumeric():
        skipped += 1
        continue
    face_indexer.names[face_id] = name
    mapped += 1

print(f"mapped {mapped}, skipped {skipped}, missed {missed}")

db['.cluster_cache'] = face_indexer


