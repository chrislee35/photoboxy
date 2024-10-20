from sklearn.cluster import AgglomerativeClustering

class Clusterer:
    @staticmethod
    def cluster(embeddings: list[list[float]], distance_threshold: float=1.0) -> list[int]:
        # Cluster features
        face_ids = AgglomerativeClustering(n_clusters=None, distance_threshold=distance_threshold, linkage='single').fit_predict(embeddings)
        return face_ids.astype(int)

