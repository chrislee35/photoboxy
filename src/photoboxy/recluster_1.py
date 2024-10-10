import diskcache
import json

dest_dir = "/home/chris/Jungle/photoboxy"
db = diskcache.Index(dest_dir+'/.db')
face_indexer = db['.cluster_cache']

cluster_1 = face_indexer.faces[1]

bboxes = []
embeddings = []
filenames = []
# for every file in the database, not just those that were updated
for filename in cluster_1:
    # skip the clustering cache
    if filename == '.cluster_cache': continue
    # get the data
    data = json.loads(db.get(filename))
    # see if the file has embeddings, this test is cheaper than testing if the file still exists
    if 'metadata' not in data: continue
    if 'embeddings' not in data['metadata']: continue
    # put each embedding, since an image can have multiple faces, into an embeddings list
    # keep the filename and bounding box in a list so that we can join the answer back into the metadata
    for embed in data['metadata']['embeddings']:
        filenames.append(filename)
        embeddings.append(embed['embed'])
        bboxes.append(embed['bbox'])
# run the clustering algorithm
tags = face_indexer._cluster(filenames, bboxes, embeddings, 3, 0.5)
print(len(list(set([x['face_id'] for x in tags]))))

if True:
    # remove the enormous cluster #1
    face_indexer.remove_all_tags_for_face(1)
    # get the unique face_ids
    face_ids = list(set([x['face_id'] for x in tags]))
    # add the new face_ids, remapping all of them to new ids
    face_id_map = {}
    next_face_id = max(list(face_indexer.faces.keys())) + 1
    for fid in face_ids:
        print(f"Adding {fid} as {next_face_id}")
        face_indexer.faces[next_face_id] = []
        face_indexer.names[next_face_id] = str(next_face_id)
        face_id_map[fid] = next_face_id
        next_face_id += 1

    # add the newly tagged clusters
    for tag in tags:
        fid = face_id_map[tag['face_id']]
        face_indexer.tag_face(tag['filename'], tag['bbox'], fid)

db['.cluster_cache'] = face_indexer
