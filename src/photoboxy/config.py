from dataclasses import dataclass

from .pool import Pool
from .embedder import Embedder
from .photobox_db import PhotoboxDB

@dataclass
class Config:
    source_dir: str
    dest_dir: str
    htmlonly: bool
    skip_videos: bool
    skip_docs: bool
    use_pca: bool
    db: PhotoboxDB
    embedder: Embedder
    pool: Pool
