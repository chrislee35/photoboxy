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

def load_names(db_dir):
    names = {}
    with open("/home/chris/Documents/photoboxy/album/faces/names-20250331230854.js") as fh:
        data = fh.read().replace('var names = ', '').strip().rstrip(';')
        name_data = json.loads(data)
        for k,v in name_data.items():
            if not v.isnumeric():
                names[k] = v
    return names

def pair_bboxes_with_embeddings_and_tag(tagging_data):
    """ when images are tagged, the embeddings are associated with a bounding box and the tags are associated with a bounding box.  
    To associate the embeddings back to the tag, you have to match on the bounding box. """
    pairs = []
    for tag in tagging_data['tags']:
        face_id = int(tag['face_id'])
        bbox = tag['bbox']
        for embedding in tagging_data['embeddings']:
            if bbox == embedding['bbox']:
                pairs.append((embedding['embed'], face_id))
                break
    return pairs

def get_cluster_data(db_dir):
    db = diskcache.Index(db_dir)
    faces = db.get('.faces', {})
    names = load_names(db_dir)
    embeddings = []
    face_ids = []
    name_tags = []
    embeddings_untagged = []

    for filename in db.keys():
        # skip the clustering cache or other special entries
        if filename.startswith("."): continue
        # get the data
        data = db.get(filename)
        # see if the file has embeddings, this test is cheaper than testing if the file still exists
        if 'embeddings' not in data: continue
        if 'tags' not in data: continue
        pairs = pair_bboxes_with_embeddings_and_tag(data)
        for pair in pairs:
            embedding, face_id = pair
            if str(face_id) in names:
                embeddings.append(embedding)
                face_ids.append(face_id)
                name_tags.append(names[str(face_id)])
            else:
                embeddings_untagged.append(embedding)
                
    embeddings_untagged_sample = random.sample(embeddings_untagged, 2000)
    return np.array(embeddings), np.array(face_ids), np.array(name_tags), np.array(embeddings_untagged_sample)

def cosine_similarity(a, b):
    """
    Compute cosine similarity between two vectors or between
    one vector and a batch of vectors.

    Parameters:
        a (np.ndarray): Vector or batch [n_features] or [n_a, n_features].
        b (np.ndarray): Vector or batch [n_features] or [n_b, n_features].

    Returns:
        float or np.ndarray: similarity values in [-1, 1].
    """
    a = np.atleast_2d(a)
    b = np.atleast_2d(b)

    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True)

    return np.dot(a_norm, b_norm.T).squeeze()


def assign_tag_simple(new_vector, previous_vector_tags, threshold=0.3):
    """
    Assigns a tag using cosine similarity against refined cluster centroids.
    
    Parameters:
        new_vector (np.ndarray): New embedding vector [n_features].
        refined_clusters (list): Output of describe_clusters_refined().
        threshold_factor (float): Determines how strict the similarity threshold is.
    
    Returns:
        (best_tag, best_similarity) or (None, best_similarity)
    """
    new_vector = np.array(new_vector).reshape(1, -1)

    best_tag, best_sim = None, -1.0

    for embedding, tag_id in previous_vector_tags:
        sim = cosine_similarity(new_vector, embedding)

        if sim > best_sim:
            best_sim = sim
            best_tag = tag_id

    if best_sim >= threshold:
        return best_tag, best_sim
    else:
        return None, best_sim

def evaluate_assignments_simple(X, tags, previous_vector_tags, threshold=0.3):
    predicted = []
    rejected = 0

    for vec, true_tag in zip(X, tags):
        pred_tag, sim = assign_tag_simple(vec, previous_vector_tags, threshold)
        if pred_tag is None:
            rejected += 1
            predicted.append("untagged")
        else:
            predicted.append(pred_tag)

    tags_arr = np.array(tags)
    pred_arr = np.array(predicted)
    mask = pred_arr != "untagged"
    accuracy = (tags_arr[mask] == pred_arr[mask]).mean() if mask.sum() > 0 else 0.0
    reject_rate = rejected / len(tags)

    print("=== Cosine Refined Evaluation Summary ===")
    print(f"Accuracy (on assigned): {accuracy:.3f}")
    print(f"Rejection rate: {reject_rate:.3f}")

    #c = Counter(predicted)
    #print(c)

    return {
        "accuracy_on_assigned": float(accuracy),
        "rejection_rate": float(reject_rate),
        "total_samples": len(tags),
        "assigned_samples": int(mask.sum()),
        "rejected_samples": rejected
    }

def remove_rare_clusters(X, tags, min_count=2):
    """
    Removes samples belonging to clusters/tags that have fewer than `min_count` members.

    Parameters:
        X (np.ndarray): Embedding matrix [n_samples, n_features].
        tags (list or np.ndarray): Cluster/tag ids per sample.
        min_count (int): Minimum number of samples required per cluster.

    Returns:
        (X_filtered, tags_filtered, removed_tags)
    """
    tags = np.array(tags)
    counts = Counter(tags)

    # Determine which tags are sufficiently populated
    keep_tags = {tag for tag, count in counts.items() if count >= min_count}
    remove_tags = [tag for tag in counts if tag not in keep_tags]

    # Create mask for samples to keep
    mask = np.array([t in keep_tags for t in tags])

    X_filtered = X[mask]
    tags_filtered = tags[mask]

    print(f"Removed {len(remove_tags)} rare tag(s): {remove_tags}")
    print(f"Remaining samples: {len(tags_filtered)} (from {len(tags)})")

    return X_filtered, tags_filtered, remove_tags

if __name__ == "__main__":
    X, tags, names, untagged = get_cluster_data('~/Documents/photoboxy/.db')
    X, names, _ = remove_rare_clusters(X, names)
    none_names = np.full(untagged.shape[0], "untagged", dtype=object)

    X_train, X_test, names_train, names_test = train_test_split(
        X,
        names,
        test_size=108,       # 1 for testing
        random_state=42,     # ensures reproducibility
        stratify=names        # keeps class proportions balanced
    )

    previous_vector_tags = list(zip(X_train, names_train))

    tr = 0.001

    evaluate_assignments_simple(X_test, names_test, previous_vector_tags, tr)
    evaluate_assignments_simple(untagged, none_names, previous_vector_tags, tr)
