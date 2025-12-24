from diskcache.persistent import Index  # pyright: ignore[reportMissingTypeStubs]
from dataclasses import dataclass
from typing import Callable, Any
from collections.abc import Generator

# Photos can have faces
# Faces have a bounding box on the photo (in the original photo's coordinates); a tag_id; and an embedding
# Tags have a tag_id, labels, and a list of photos that contain that tag
#   this is so that we can find all the photos tagged with that tag_id
# Not all tags are for faces, you can tag a photo for many things
# 

@dataclass
class ClusterDescription:
    centroid: list[float]
    mean_dist: float
    max_dist: float
    count: int

@dataclass
class Tag:
    id: int
    label: int | str
    photos: set[str]
    description: ClusterDescription | None

@dataclass
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float

@dataclass
class Face:
    bbox: BoundingBox
    embedding: list[float] | None
    tag_id: int | None

@dataclass
class Photo:
    filepath: str
    mtime: str
    size: int
    sort_key: str
    metadata: dict[str, Any]  # pyright: ignore[reportExplicitAny]
    relpath: str
    date: str
    faces: list[Face]

class PhotoboxDB:
    """ PhotosDB provides the database functions for Photoboxy """
    def __init__(self, database_dir:str = ".db"):
        # Opens a diskcache database at the given location
        self.db: Index = Index(database_dir)
        if '.tags' not in self.db:
            self.db['.tags'] = set()
    
    def get_tag(self, tag_id: int) -> Tag | None:
        """ This retrieves the Tag(id, label, photos, description) of a given tag_id """
        return self.db.get(f'.tag{tag_id}')  # pyright: ignore[reportUnknownVariableType]
    
    def get_photo(self, filepath: str) -> Photo | None:
        """ This returns the PhotoRec(filepath, mtime, size, sort_key, metadata, relpath, date, faces) of a photo identify by the source filepath """
        return self.db.get(filepath)  # pyright: ignore[reportUnknownVariableType]

    def add_face_to_photo(self, filepath: str, left: float, top: float, right: float, bottom: float, 
        embedding: list[float] | None=None, tag_id: int | None = None) -> bool:
        """ Adds a bounding box onto a photo to define a face.
        The left, top, right, and bottom are coordinates in the original photo, not the resized one.
        embedding and tag_id are optional
        """
        photo: Photo | None = self.get_photo(filepath)
        if photo is None:
            return False
        new_face: Face = Face(BoundingBox(left, top, right, bottom), embedding, tag_id)
        photo.faces.append(new_face)
        self.db[filepath] = photo
        if tag_id is not None:
            res: bool = self.add_photo_to_tag(tag_id, filepath)
            return res
        return True

    def add_photo(self, photo: Photo) -> None:
        """ adds a photo record (or overwrites it) to the database """
        self.db[photo.filepath] = photo
        for face in photo.faces:
            if face.tag_id is not None:
                self.add_photo_to_tag(face.tag_id, photo.filepath)  # pyright: ignore[reportUnusedCallResult]
    
    update_photo: Callable[..., None] = add_photo  # pyright: ignore[reportUnannotatedClassAttribute]

    def add_metadata(self, filepath: str, tag: str, value: Any) -> None:  # pyright: ignore[reportAny]
        """ Adds various metadata, usually exif data, to a filepath """
        photo: Photo | None = self.get_photo(filepath)
        if photo is None:
            return
        photo.metadata[tag] = value
        self.db[filepath] = photo

    def add_new_tag(self, label: str, set_tag_id: int = -1) -> int:
        """ Adds a tag to the list of tags. returns the new tag_id """
        tags: set[int] = self.db['.tags']  # pyright: ignore[reportAssignmentType]
        tag_id: int = 1
        if len(tags) == 0:
            tag_id = 1
        else:
            tag_id = max(tags) + 1
        if set_tag_id > -1:
            tag_id = tag_id
        new_tag: Tag = Tag(id=tag_id, label=label, photos=set[str](), description=None)
        tags.add(tag_id)
        self.db['.tags'] = tags
        self.db[f'.tag{tag_id}'] = new_tag
        return tag_id

    def rename_tag(self, tag_id: int, label: str) -> bool:
        """ Changes the label on a tag """
        tag: Tag | None = self.db.get(f'.tag{tag_id}')  # pyright: ignore[reportUnknownMemberType]
        if tag is None:
            return False
        tag.label = label
        self.db[f'.tag{tag_id}'] = tag
        return True

    def remove_tag(self, tag_id: int) -> bool:
        """ Removes a tag from the database and goes through all filepaths to remove any tags """
        tags: set[int] = self.db['.tags']  # pyright: ignore[reportAssignmentType]
        if tag_id not in tags:
            return False
        tag: Tag | None = self.db.get(f'.tag{tag_id}')  # pyright: ignore[reportUnknownMemberType]
        if tag is None:
            return False
        
        for filepath in tag.photos:
            # set the tag_id to None
            self.untag_face(tag_id, filepath)
        self.db.pop(f'.tag{tag_id}')
        tags.remove(tag_id)
        self.db['.tags'] = tags
        return True

    def tags(self) -> list[Tag]:
        """ returns the Tag(id, label, photos, description) for all the tags """
        tags: set[int] = self.db['.tags']  # pyright: ignore[reportAssignmentType]
        return [self.db.get(f'.tag{tag_id}') for tag_id in tags]  # pyright: ignore[reportUnknownVariableType, reportReturnType]

    def add_photo_to_tag(self, tag_id: int, filepath: str) -> bool:
        """ Add the filepath to the list of filepaths associated with a tag """
        tag: Tag | None = self.db.get(f'.tag{tag_id}')  # pyright: ignore[reportAssignmentType]
        if tag is None:
            return False
        tag.photos.add(filepath)
        self.db[f'.tag{tag_id}'] = tag
        return True

    def remove_photo_from_tag(self, tag_id: int, filepath: str) -> bool:
        """ Remove the filepath from the list of filepaths associated with a tag """
        tag: Tag | None = self.db.get(f'.tag{tag_id}')  # pyright: ignore[reportUnknownMemberType]
        if tag is None:
            return False
        tag.photos.discard(filepath)
        self.db[f'.tag{tag_id}'] = tag
        return True

    def in_bbox(self, bbox: BoundingBox, x: float, y: float) -> bool:
        """ returns True if the x and y are within the bounding box """
        if x < bbox.left:
            return False
        if y < bbox.top:
            return False
        if x > bbox.right:
            return False
        if y > bbox.bottom:
            return False
        return True

    def retag_face(self, 
        filepath: str, 
        old_tag_id: int | None, 
        new_tag_id: int | None, 
        x: float | None = None, 
        y: float | None = None
    ) -> bool:
        """Retagging a tag means to change the tag_id associated with a given (or multiple) bounding boxes

        Args:
            filepath (str): source filepath of the photo
            old_tag_id (int): the current tag_id to search for and replace
            new_tag_id (int): the new tag_id to use for matching tags
            x (int, optional): if specified, it limits the replacement to just the tags that the bounding box contains the x,y. Defaults to None.
            y (int, optional): if specified, it limits the replacement to just the tags that the bounding box contains the x,y. Defaults to None.

        Returns:
            _type_: bool
        """
        photo = self.get_photo(filepath)
        if not photo:
            return False

        for face in photo.faces:
            # if coordinates are specified, check if they are in the bounding box
            if x and y:
                if not self.in_bbox(face.bbox, x, y):
                    continue
            if face.tag_id == old_tag_id:
                face.tag_id = new_tag_id
                if old_tag_id is not None:
                    self.remove_photo_from_tag(old_tag_id, filepath)  # pyright: ignore[reportUnusedCallResult]
                self.update_photo(photo) # this will add the photo's filepath to the tag's list of files
                return True
        return False

    def untag_face(self, tag_id: int, filepath: str, x: float | None = None, y: float | None = None) -> bool:
        """ set the tag_id of the matching faces to None """
        return self.retag_face(filepath, tag_id, None, x, y)
        
    def remove_face_from_photo(self, tag_id: int, filepath: str, x: float | None = None, y: float | None = None) -> bool:
        """ remove the matching faces, along with their bounding boxes """
        photo: Photo | None = self.get_photo(filepath)
        if not photo:
            return False
        
        remove_indexes: list[int] = []
        for idx, face in enumerate(photo.faces):
            # if coordinates are specified, check if they are in the bounding box
            if x and y:
                if not self.in_bbox(face.bbox, x, y):
                    continue
            if face.tag_id == tag_id:
                remove_indexes.append(idx)

        if len(remove_indexes) == 0:
            return False
        
        photo.faces = [face for idx, face in enumerate(photo.faces) if idx not in remove_indexes]
        # if there are multiple faces with the same tag_id, this will remove all of them, but update_photo will add it back
        self.remove_photo_from_tag(tag_id, filepath)  # pyright: ignore[reportUnusedCallResult]
        self.update_photo(photo)
        return True

    def filepaths(self) -> list[str]:
        """ returns the list of all the filepaths """
        return [x for x in self.db.keys() if not x.startswith('.')]  # pyright: ignore[reportReturnType, reportUnknownVariableType, reportUnknownMemberType, reportOptionalMemberAccess, reportArgumentType]

    def photos(self) -> Generator[Photo, None, None]:
        """ yields/generator for all Photo Records """
        for filepath in self.filepaths():
            photo: Photo | None = self.get_photo(filepath)
            if photo:
                yield photo
