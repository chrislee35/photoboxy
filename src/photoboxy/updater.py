import os
import time
from typing import Callable
from threading import Thread
from collections import Counter

from PIL.Image import Image as PILImage

from .directory import Directory
from .pool import Pool
from .clusterer import Clusterer
from .embedder import Embedder
from .face_tag_manager import FaceTagManager
from .timeline_manager import TimelineManager
from .photobox_db import BoundingBox, PhotoboxDB, Photo, Tag, Face
from .template_manager import PhotoboxTemplate, TemplateManager
from .config import Config

class Updater:
    # through away clusters that don't have enough images to make them worth while
    # i.e., the face cluster must appear in at least {CLUSTER_OCCURANCE} images to be considered
    CLUSTER_OCCURANCE: int = 5
    # this cluster distance controls how close two sets of pictures embeddings must be to even be considered as 
    # one cluster
    CLUSTER_DISTANCE: float = 1.0

    def __init__(self, fullpath: str, dest_dir: str) -> None:
        self.stats: dict[str, dict[str, int] | int] = {
            'total': {
                'folder': 1, # for the inputroot
                'image': 0,
                'video': 0,
                'note': 0,
            },
            'changed': {
                'folder': 0,
                'image': 0,
                'video': 0,
                'note': 0,
            },
            'generated': {
                'folder': 0,
                'image': 0,
                'video': 0,
                'note': 0,
            },
            'skipped': 0
        }
        self.changes: list[str] = []
        self.state: str = 'initialized'

        # open or create database in read/write mode with synchronization on writes
        db: PhotoboxDB = PhotoboxDB(database_dir=".db")
        
        pool: Pool = Pool()
        embedder: Embedder = Embedder()

        self.config: Config = Config(
            source_dir=fullpath,
            dest_dir=dest_dir,
            htmlonly=False,
            skip_videos=False,
            skip_docs=False,
            use_pca=False,
            db=db,
            embedder=embedder,
            pool=pool
        )

        self.directory: Directory = Directory(fullpath=fullpath, relpath='', config=self.config)

        self.print_stats_thread: Thread = Thread(target=self.print_stats_continuous)
        self.timestamps: dict[str, float | None] = {
            'init': time.time(),
            'enum_s': None,
            'enum_e': None,
            'gen_s': None,
            'gen_e': None
        }
        
    def add_change(self, type: str, filename: str) -> None:
        self.stats['changed'][type] += 1  # pyright: ignore[reportIndexIssue]
        self.changes.append(filename)
    
    def add_total(self, type: str) -> None:
        self.stats['total'][type] += 1  # pyright: ignore[reportIndexIssue]
        
    def add_skip(self) -> None:
        self.stats['skipped'] += 1  # pyright: ignore[reportOperatorIssue]

    def add_generated(self, type: str) -> None:
        self.stats['generated'][type] += 1  # pyright: ignore[reportIndexIssue]
    
    def enumerate(self) -> None:
        self.state = 'enumerating'
        self.timestamps['enum_s'] = time.time()
        self.print_stats_thread.start()
        for item in self.directory.enumerate():
            if item is None:
                continue
            self.stats['total'][item.type] += 1  # pyright: ignore[reportIndexIssue]
            if item.changed:
                self.stats['changed'][item.type] += 1  # pyright: ignore[reportIndexIssue]
            self.changes.append(item.path)
        self.state = 'enumerated'
        self.timestamps['enum_e'] = time.time()

    def embed(self, img: PILImage) -> list[dict[str, float]]:
        return self.config.embedder.embed(image=img)

    def needs_clustering(self) -> bool:
        """ Decide if FaceIndexer should rerun the clustering algorithm """
        # if there are changed images that have faces (embeddings) in them
        for changed in self.changes:
            data: Photo | None = self.config.db.get_photo(filepath=changed)
            if data and len(data.faces) > 0:
                return True
                
        return False

    def cluster(self) -> None:
        self.state = 'clustering'
        self.timestamps['cluster_s'] = time.time()
        bboxes: list[BoundingBox] = []
        embeddings: list[list[float]] = []
        filenames: list[str] = []
        # keeps track of which images were already tagged before clustering
        already_tagged: set[str] = set[str]()
        
        # for every file in the database, not just those that were updated
        for filename in self.config.db.filepaths():
            # get the data
            photo: Photo | None = self.config.db.get_photo(filepath=filename)
            if photo is None:
                continue
            # see if the file has embeddings, this test is cheaper than testing if the file still exists
            faces: list[Face] = photo.faces
            if len(faces) == 0:
                continue
            embeds: list[list[float]] = [face.embedding for face in faces if face.embedding]
            if not embeds:
                continue
            # make sure that the source still exists
            if not os.path.exists(path=filename):
                continue
            # track which images already have tags
            tags: list[int] = [face.tag_id for face in faces if face.tag_id]
            if tags:
                already_tagged.add(filename)

            # put each embedding, since an image can have multiple faces, into an embeddings list
            # keep the filename and bounding box in a list so that we can join the answer back into the metadata
            for face in photo.faces:
                if face.embedding:
                    filenames.append(photo.filepath)
                    embeddings.append(face.embedding)
                    bboxes.append(face.bbox)

        # check if there are any faces
        if len(embeddings) == 0:
            return

        # run the clustering algorithm
        face_ids: list[int] = Clusterer.cluster(embeddings, distance_threshold=Updater.CLUSTER_DISTANCE, use_pca=self.config.use_pca)
        # filter for the minimum occurance requirement
        c: Counter[int] = Counter[int](face_ids)
        keep: set[int] = set[int]([x for x in c if c[x] >= Updater.CLUSTER_OCCURANCE])
        for face_id, filename, bbox in zip(face_ids, filenames, bboxes):
            # don't retag photos that are already tagged
            if filename in already_tagged:
                continue
            # don't add tags that don't meet the minimum occurance
            if face_id not in keep:
                continue
            # get the file's record from the database
            photo = self.config.db.get_photo(filepath=filename)
            if not photo:
                continue

            tag: Tag | None = self.config.db.get_tag(tag_id=face_id)
            if tag is None:
                self.config.db.add_new_tag(label=str(face_id), set_tag_id=face_id)  # pyright: ignore[reportUnusedCallResult]
            
            for face in photo.faces:
                if bbox == face.bbox:
                    face.tag_id = face_id
                    self.config.db.add_photo_to_tag(tag_id=face_id, filepath=filename)  # pyright: ignore[reportUnusedCallResult]
                    break
    
    def generate(self, dest_dir: str, template_name: str = 'boring') -> None:
        self.state = 'generating'
        self.timestamps['gen_s'] = time.time()
        templates: PhotoboxTemplate | None = TemplateManager.get_templates(scheme_name=template_name)
        # create the tag_manager here because the database is now updated with all the files
        # and we need it available for the generation of the image files
        if templates is None:
            raise Exception(f"Could not find any templates for the template named: {template_name}")
        self.tag_manager: FaceTagManager = FaceTagManager(self.config.db)  # pyright: ignore[reportUninitializedInstanceVariable]

        for item in self.directory.generate(templates, dest_dir):
            if item is not None:
                self.stats["generated"][item.type] += 1
                
        self.config.pool.waitall()
        # the clusterer needs to know the source dir so that it can rewrite the filenames
        # into relative urls for the images and thumbnails
        self.tag_manager.generate(templates, dest_dir, self.config.source_dir)
        
        # now generate the calendar
        timeline_manager: TimelineManager = TimelineManager(self.config.db, self.config.source_dir, dest_dir)
        timeline_manager.generate_calendar()

        # finish the process
        self.state = 'generated'
        self.timestamps['gen_e'] = time.time()
        self.print_stats_thread.join()
    
    def update_template(self, dest_dir: str, template_name: str='boring') -> None:
        templates: PhotoboxTemplate | None = TemplateManager.get_templates(scheme_name=template_name)
        if templates is None:
            raise Exception(f"Could not find any templates for the template named: {template_name}")
        self.directory.update_template(templates, dest_dir)
        self.config.pool.waitall()
    
    def get_data(self, filename: str) -> Photo | None:
        data: Photo | None = self.config.db.get_photo(filepath=filename)
        return data
    
    def set_data(self, photo: Photo) -> None:
        if not photo.relpath:
            photo.relpath = photo.filepath.replace(self.config.source_dir, "").lstrip('/')
        if not photo.date:
            photo.date = photo.mtime.split(sep=' ')[0]
        self.config.db.add_photo(photo)

    def fork_proc(self, proc: str | Callable[..., None], args: list[str|int]) -> None:
        self.config.pool.do_work(cmd_or_proc=proc, args=args)  # pyright: ignore[reportArgumentType]
    
    def fork_cmd(self, cmd: str) -> None:
        self.config.pool.do_work(cmd_or_proc=cmd)

    def print_stats_monitor(self) -> None:
        # TODO: figure out how to stop this if the user only wants to enumerate
        while self.state != 'generated':
            self.print_stats()
            time.sleep(1)

    def print_stats_enumerating(self, last_len: int) -> int:
        t: dict[str, int] = self.stats['total']  # pyright: ignore[reportAssignmentType]
        c: dict[str, int] = self.stats['changed']  # pyright: ignore[reportAssignmentType]
        tt: int = sum( [t['folder'], t['image'], t['video'], t['note']] )
        ct: int = sum( [c['folder'], c['image'], c['video'], c['note']] )
        folder_s: str = f"{t['folder']}/{c['folder']}"
        image_s: str = f"{t['image']}/{c['image']}"
        video_s: str = f"{t['video']}/{c['video']}"
        note_s: str = f"{t['note']}/{c['note']}"
        total_s: str = f"{tt}/{ct}"
        if last_len > 0:
            print("\b" * last_len, end="", flush=True)
        line: str = f"Enumerated {folder_s:14s} {image_s:14s} {video_s:14s} {note_s:14s} {total_s:14s}"
        print(line, end="", flush=True)
        return len(line)

    def print_stats_continuous(self) -> None:
        print(f"State: {self.state}")
        print( "           Folders        Images         Videos         Notes          Total")
        last_len: int = 0  # pyright: ignore[reportRedeclaration]
        while self.state in ['initialized','enumerating']:
            last_len = self.print_stats_enumerating(last_len)
            time.sleep(1)
        
        print()
        print("Clustering")
        
        line_count: int = 0
        while self.state in ['clustering']:
            print(".", end="", flush=True)
            line_count += 1
            if line_count == 10:
                print(("\b" * 10)+(" " * 10)+("\b" * 10), end="", flush=True)
                line_count = 0
            time.sleep(0.5)

        print()
        print( "            Folders   Images   Videos    Notes    Total")
        last_len = 0
        while self.state in ['generating']:
            metric: dict[str, int] = self.stats['generated']  # pyright: ignore[reportAssignmentType]
            folder: int = metric['folder']
            image: int = metric['image']
            video: int = metric['video']
            note: int = metric['note']
            total: int = sum([folder, image, video, note])
            if last_len > 0:
                print("\b" * last_len, end="", flush=True)
            line: str = f"Generated  {folder : 8d} {image : 8d} {video : 8d} {note : 8d} {total : 8d}"
            last_len: int = len(line)
            print(line, end="", flush=True)
            time.sleep(1)

    def print_stats(self) -> None:
        metric: dict[str, int] = self.stats['total']  # pyright: ignore[reportAssignmentType]
        folder: int = metric['folder']
        image: int = metric['image']
        video: int = metric['video']
        note: int = metric['note']
        total: int = sum([folder, image, video, note])

        print(f"State: {self.state}")
        print( "           Folders  Images  Videos   Notes      Total")
        print(f"Enumerated {folder : 7d} {image : 7d} {video : 7d} {note : 7d} {total : 10d}")

        metric = self.stats['changed']  # pyright: ignore[reportAssignmentType]
        folder = metric['folder']
        image = metric['image']
        video = metric['video']
        note = metric['note']
        total = sum([folder, image, video, note])
        
        print(f"Changed    {folder : 7d} {image : 7d} {video : 7d} {note : 7d} {total : 10d}")
        
        metric = self.stats['generated']  # pyright: ignore[reportAssignmentType]
        folder = metric['folder']
        image = metric['image']
        video = metric['video']
        note = metric['note']
        total = sum([folder, image, video, note])

        print(f"Generated  {folder : 7d} {image : 7d} {video : 7d} {note : 7d} {total : 10d}")
        print(f"Enumeration took {self.timestamps['enum_e'] - self.timestamps['enum_s'] : 0.2f}s  Generation took {self.timestamps['gen_e'] - self.timestamps['gen_s'] : 0.2f}s")  # pyright: ignore[reportOperatorIssue]
