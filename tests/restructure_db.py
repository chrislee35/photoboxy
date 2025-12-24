import diskcache
import json
import sqlite3
import sqlite_vec
import os
from datetime import datetime
from pathlib import Path
from typing import Optional
from tqdm import tqdm

class PhotoboxyDatabaseConverter:
    def __init__(self, photoboxy_root):
        self.diskcache_dir = os.path.join(photoboxy_root, '.db')
        self.tags_file = os.path.join(photoboxy_root, "album", "faces", "names-20250331230854.js")
        self.sqlite3_file = os.path.join(photoboxy_root, ".db", "photos.sqlite3")

    def initialize_photo_db(self):
        """
        Initialize an SQLite database for a photo album system.

        Creates four tables:
            - photos: metadata for each photo
            - exif: EXIF key/value pairs, each linked to a photo
            - faces: detected faces and bounding boxes, linked to a photo
            - embeddings: vector embeddings for each detected face (uses sqlite3-vec)

        Parameters
        ----------
        db_path : str
            Path to the SQLite database file to create or open.
        """

        db_path: str = self.sqlite3_file

        # Ensure folder exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Connect to SQLite
        conn = sqlite3.connect(db_path)

        # Load sqlite-vec extension (must be installed in the environment)
        # Errors are allowed if vec is already loaded or unavailable.
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        
        cur = conn.cursor()

        # ---- Create photos table ----
        cur.execute("""
            CREATE TABLE IF NOT EXISTS photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL UNIQUE,
                relative_path TEXT NOT NULL,
                taken_date TEXT,                  -- ISO date string or NULL
                last_modified_time REAL,          -- Unix timestamp
                size INTEGER,                     -- size in bytes
                sort_key TEXT,                    -- for album ordering
                scale REAL                        -- precomputed scaling factor for UI
            )
        """)

        # ---- Create metadata table ----
        cur.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                tag TEXT NOT NULL,
                value TEXT,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );
        """)

        # ---- Create embeddings table (sqlite3-vec) ----
        # vec column type is provided by sqlite-vec extension
        # buffalo_sc returns a 512 element float embedding vector
        cur.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS embeddings USING vec0 (
                vector float[512]
            );
        """)

        # ---- Create faces table ----
        cur.execute("""
            CREATE TABLE IF NOT EXISTS faces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                photo_id INTEGER NOT NULL,
                left REAL NOT NULL,
                top REAL NOT NULL,
                right REAL NOT NULL,
                bottom REAL NOT NULL,
                tag_id INTEGER,
                embedding_id INTEGER NOT NULL,
                FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
            );
        """)

        # ---- Create a table for the name tags ----
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT
            );
        """)


        # Commit changes and close
        conn.commit()
        conn.close()

        print(f"Database initialized at: {db_path}")

    def load_tags(self):
        with open(self.tags_file) as fh:
            data = fh.read().replace('var names = ', '').strip().rstrip(';')
            name_data = json.loads(data)
            return name_data

    def insert_face(self, photo_id: int, left: int, top: int, right: int, bottom: int, tag_id: Optional[int], embedding_id: id) -> int:
        self.cursor.execute("INSERT INTO faces (photo_id, left, top, right, bottom, tag_id, embedding_id) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (photo_id, left, top, right, bottom, tag_id, embedding_id))
        return self.cursor.lastrowid

    def insert_metadata(self, photo_id: int, tag: str, value: str):
        self.cursor.execute("INSERT INTO metadata (photo_id, tag, value) VALUES (?, ?, ?)", (photo_id, tag, str(value)))

    def insert_photo(self, filename: str, relative_path: str, taken_date: str, last_modified_time: int, size: int, sort_key: str, scale: float) -> int:
        self.cursor.execute("INSERT INTO photos (filename, relative_path, taken_date, last_modified_time, size, sort_key, scale) VALUES (?, ?, ?, ?, ?, ?, ?)", 
            (filename, relative_path, taken_date, last_modified_time, size, sort_key, scale))
        return self.cursor.lastrowid

    def insert_vector(self, vector: list[float]) -> int:
        self.cursor.execute("INSERT INTO embeddings (vector) VALUES (?)", [sqlite_vec.serialize_float32(vector)])
        return self.cursor.lastrowid

    def insert_tags(self, all_tags: list[tuple[int, str]]):
        with sqlite3.connect(self.sqlite3_file) as conn:
            curr = conn.cursor()
            curr.executemany("INSERT OR IGNORE INTO tags (id, name) VALUES (?, ?)", all_tags)

    def get_data(self, filename: str):
        with sqlite3.connect(self.sqlite3_file) as conn:
            curr = conn.cursor()
            curr.execute("SELECT id, filename, relative_path, taken_date, last_modified_time, size, sort_key, scale FROM photos WHERE filename = ?", (filename,))

    def transfer_database(self):
        print("Initializing database")
        self.initialize_photo_db()

        db_dir = self.diskcache_dir
        db = diskcache.Index(db_dir)
        tags = self.load_tags()

        all_tags = [(tag_id, tag) for tag_id, tag in tags.items()]
        self.insert_tags(all_tags)

        for filename in tqdm(db.keys()):
            # skip the clustering cache or other special entries
            if filename.startswith("."): continue
            # get the data
            data = db.get(filename)
            try:
                relative_path = data['relpath']
                taken_date = data['date']
                last_modified_time = datetime.strptime(data['mtime'], '%Y-%m-%d %H:%M:%S %Z').timestamp()
                size = data['size']
                sort_key = data['sort_key']
                scale = data.get('scale', 1.0)
            except Exception as e:
                print(e)
                print(filename)
                print(data.keys())
                exit()
            
            self.connection = sqlite3.connect(self.sqlite3_file)
            self.connection.enable_load_extension(True)
            sqlite_vec.load(self.connection)
            self.cursor = self.connection.cursor()

            # add the photo/video entry to the db
            photo_id = self.insert_photo(filename, relative_path, taken_date, last_modified_time, size, sort_key, scale)
            # add the metadata
            if data.get('metadata'):
                for tag, value in data['metadata'].items():
                    self.insert_metadata(photo_id, tag, value)
            # add faces based on the embedded bboxes, with tags if tagged
            
            if data.get('embeddings'):
                for rec in data['embeddings']:
                    vector = rec['embed']
                    bbox = rec['bbox']
                    face_id = None
                    for tag in data.get('tags', []):
                        if tag['bbox'] == bbox:
                            tag_id = tag['face_id']
                            break
                    embedding_id = self.insert_vector(vector)
                    face_id = self.insert_face(photo_id, bbox[0], bbox[1], bbox[2], bbox[3], tag_id, embedding_id)
            
            self.connection.commit()
            self.connection.close()

    def transfer_database2(self):
        db_dir = self.diskcache_dir
        db = diskcache.Index(db_dir)

        dest_db = diskcache.Index(db_dir+"2")
        tags = self.load_tags()
        faces = {}
        for tag_id in db['.faces'].keys():
            faces[tag_id] = { 'label': tags.get(tag_id, tag_id), 'photos': db['.faces'][tag_id] }

        dest_db['.faces'] = faces


        for filename in tqdm(db.keys()):
            # skip the clustering cache or other special entries
            if filename.startswith("."): continue
            # get the data
            data = db.get(filename)
            data['faces'] = []
            
            if data.get('embeddings'):
                for rec in data['embeddings']:
                    vector = rec['embed']
                    bbox = rec['bbox']
                    tag_id = None
                    for tag in data.get('tags', []):
                        if tag['bbox'] == bbox:
                            tag_id = tag['face_id']
                            break
                    data['faces'].append({
                        'bbox': rec['bbox'],
                        'embedding': rec['embed'],
                        'tag_id': tag_id
                    })
                data.pop('embeddings')
            dest_db[filename] = data

if __name__ == "__main__":
    import sys
    photoboxy_path = sys.argv[1]
    pdc = PhotoboxyDatabaseConverter(photoboxy_path)
    import time
    st = time.time()
    pdc.transfer_database2()
    et = time.time()
    print(f"Transfer took {et-st:0.2f} seconds")







