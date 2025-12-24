import diskcache
import numpy as np
import json
import random
from collections import defaultdict
from collections import Counter
from sklearn.metrics import confusion_matrix, classification_report

from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from scipy.stats import describe
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity

def get_cluster_data(db_dir):
    db = diskcache.Index(db_dir)
    faces = db.get('.faces', {})
    embeddings = []
    face_ids = []
    name_tags = []

    for filename in db.keys():
        # skip the clustering cache or other special entries
        if filename.startswith("."): continue
        # get the data
        data = db.get(filename)
        # see if the file has embeddings, this test is cheaper than testing if the file still exists
        if 'faces' not in data: continue
        for face in data['faces']:
            embedding = face['embedding']
            face_id = face['tag_id']
            if face_id is not None:
                embeddings.append(embedding)
                face_ids.append(face_id)

    return np.array(embeddings), np.array(face_ids)

def describe_clusters(X, tags):
    """
    Compute centroid and radius (average + max distance) for each cluster/tag.

    Parameters:
        X (np.ndarray): Embedding matrix [n_samples, n_features].
        tags (list or np.ndarray): Cluster/tag ids per sample.

    Returns:
        dict: {
            tag_id: {
                "centroid": np.ndarray,
                "mean_dist": float,
                "max_dist": float,
                "count": int
            }
        }
    """
    cluster_desc = {}
    tags = np.array(tags)

    for tag_id in np.unique(tags):
        mask = tags == tag_id
        cluster_points = X[mask]
        centroid = cluster_points.mean(axis=0)
        dists = np.linalg.norm(cluster_points - centroid, axis=1)
        cluster_desc[int(tag_id)] = {
            "centroid": centroid.tolist(),
            "mean_dist": float(dists.mean()),
            "max_dist": float(dists.max()),
            "count": int(len(cluster_points))
        }

    return cluster_desc

if __name__ == "__main__":
    import time
    db_dir = '~/Documents/photoboxy/.db2'
    db = diskcache.Index(db_dir)
    faces = db.get('.faces', {})
    st = time.time()
    X, tags = get_cluster_data(db_dir)
    et = time.time()
    print(f"Loading took {et-st:0.2f}s")
    cluster_desc = describe_clusters(X, tags)
    st = time.time()
    print(f"Clustering took {st-et:0.2f}s")
    found = 0
    not_found = 0
    for cluster_id in cluster_desc.keys():
        if cluster_id in faces:
            faces[cluster_id]['description'] = cluster_desc[cluster_id]
            found += 1
        else:
            not_found += 1
    db['.faces'] = faces
    print(f"Found {found} Not {not_found}")
