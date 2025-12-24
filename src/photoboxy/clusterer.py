from collections import Counter
from sklearn.cluster import AgglomerativeClustering
from sklearn.decomposition import PCA
import numpy as np

class Clusterer:
    @staticmethod
    def cluster(embeddings: list[list[float]], distance_threshold: float=1.0, use_pca: bool=False, pca_n_components: int =32) -> list[int]:
        # use pca if enabled.
        if use_pca:
            pca: PCA = PCA(n_components=pca_n_components)
            _ = pca.fit(X=embeddings)  # pyright: ignore[reportUnknownMemberType]
            embeddings = pca.transform(X=embeddings)  # pyright: ignore[reportUnknownMemberType]

        # Cluster features
        face_ids: np.ndarray = AgglomerativeClustering(
            n_clusters=None, 
            distance_threshold=distance_threshold, 
            linkage='single'
        ).fit_predict(X=embeddings)

        seen: set[int] = set[int](face_ids)
        counts: Counter[int] = Counter[int](face_ids)
        # if any cluster is too large, then we need to set it aside and recluster it
        max_cluster_size: int = int(len(embeddings)/10)
        large_clusters: list[int] = [ face_id for face_id, cnt  in counts.items() if cnt > max_cluster_size ]

        for fid in large_clusters:
            ind = np.where(face_ids==fid)
            new_face_ids = AgglomerativeClustering(
                n_clusters=None, 
                distance_threshold=distance_threshold/2.0, 
                linkage='single'
            ).fit_predict(X=np.array(embeddings)[ind])
            face_ids[ind] = new_face_ids

        return face_ids.tolist()

