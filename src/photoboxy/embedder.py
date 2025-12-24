from insightface.app.face_analysis import FaceAnalysis  # pyright: ignore[reportMissingTypeStubs]
from PIL.Image import Image as PILImage
import numpy as np

class Embedder:
    def __init__(self):
        root = '.embedder'
        self.app: FaceAnalysis = FaceAnalysis(name='buffalo_sc', root=root) # use fast models in buffalo_sc
        self.app.prepare(ctx_id=0)
    
    def embed(self, image: PILImage) -> list[dict[str, list[float]]]:
        img = np.array(image.convert(mode='RGB'))
        faces = self.app.get(img)
        return [ {'embed': face.normed_embedding.tolist(), 'bbox': face.bbox.tolist()} for face in faces ]
