import time
import os
import glob
import json
from shutil import copyfile

from .photobox_db import Face, Photo, PhotoboxDB, Tag
from .template_manager import PhotoboxTemplate

class FaceTagManager:
    def __init__(self, db: PhotoboxDB) -> None:
        self.db: PhotoboxDB = db

    def save(self) -> None:
        pass

    def get_tags(self, filename: str) -> list[Face]:
        photo: Photo | None = self.db.get_photo(filepath=filename)
        if photo is None:
            return []
        return photo.faces
    
    def in_bbox(self, bbox: list[float], x: float, y: float) -> bool:
        if x < bbox[0]: return False
        if y < bbox[1]: return False
        if x > bbox[2]: return False
        if y > bbox[3]: return False
        return True
    
    def retag(self, filename: str, old_face_id: int, new_face_id: int, x: int | None=None, y: int | None=None) -> bool:
        return self.db.retag_face(filepath=filename, old_tag_id=old_face_id, new_tag_id=new_face_id, x=x, y=y)

    def add_new_facename(self, name: str) -> int:
        face_id: int = self.db.add_new_tag(label=name)
        return face_id

    def rename_faceid(self, face_id: int, name: str) -> None:
        """This changes the name associated with the face_id, updating all tags using that face_id"""
        self.db.rename_tag(tag_id=face_id, label=name)

    def tag_face(self, filename: str, bbox: list[float], face_id: int) -> bool:
        """record the association of a bbox in a filename to a face_id"""
        # I can't calculate a face embedding on a given bbox, so it just stays None
        success: bool = self.db.add_face_to_photo(
            filepath=filename, left=bbox[0], top=bbox[1], right=bbox[2], bottom=bbox[3], embedding=None, tag_id=face_id)
        success2: bool = self.db.add_photo_to_tag(tag_id=face_id, filepath=filename)
        return success and success2

    def remove_tag(self, filename: str, face_id: int, x: int|None=None, y: int|None=None) -> bool:
        """ This removes the association of one or more face_id tags from a photo 
        if coordinates x and y are given, then it will limit it to just that one tagging """
        return self.db.remove_face_from_photo(tag_id=face_id, filepath=filename, x=x, y=y)

    def remove_tag_folder(self, folder: str) -> tuple[int, int]:
        """ This removes all face_id tags from all photos within a folder AND its children """
        photo_count = 0
        tag_count = 0
        for photo in self.db.photos():
            if photo.filepath.startswith(folder+'/'):
                photo_count += 1
                for tag in photo.faces:
                    tag_count += 1
                    if tag.tag_id is not None:
                        self.db.remove_photo_from_tag(tag_id=tag.tag_id, filepath=photo.filepath)  # pyright: ignore[reportUnusedCallResult]
        return photo_count, tag_count

    def remove_all_tags_for_face(self, face_id: int) -> bool:
        """ Remove all tags for a face_id and then remove the record for the face_id
         this removes that face completely from the index """
        return self.db.remove_tag(tag_id=face_id)

    def generate(self, templates: PhotoboxTemplate, dest_dir: str, source_dir: str) -> None:
        # 1st, make the destination directories
        faces_dir: str = dest_dir+'/faces'
        res_dir: str = faces_dir+'/res'
        os.makedirs(name=res_dir, exist_ok=True)
        # 2nd, remove previous cluster pages since the clusters may be different and not use all the same
        # cluster numbers as previous runs
        for fn in glob.glob(pathname=faces_dir+'*.html'):
            os.unlink(path=faces_dir+fn)

        # 3th, copy over the resources
        # for each resource, copy it over
        for f in os.scandir(templates.res):
            item: str = f.name
            copyfile(src=f"{templates.res}/{item}", dst=f"{res_dir}/{item}")  # pyright: ignore[reportUnusedCallResult]

        # 4th, sort the clusters by length, longest first
        tags: list[Tag] = self.db.tags()
        tags.sort(key=lambda x: len(x.photos), reverse=True)

        # 4th and a half, create a list for the index page to keep the first image thumbname and webpage for each cluster
        tags_index: list[dict[str, str]] = []

        # 5th, enumerate through the order cluster names, so that we can determine next and previous clusters for the template
        for index, tag in enumerate[Tag](tags):
            # determine the next and previous clusters
            prev_item: Tag | None = None
            next_item: Tag | None = None
            if index > 0:
                prev_item = tags[index - 1]
            if index < len(tags) - 1:
                next_item = tags[index + 1]
            
            # 6th, wrap the webpage and thumbnail urls into a list of dictionaries for the template
            # this is tricky
            images: list[dict[str, str]] = []
            fewest_c = 10000 # used to add the photo with the fewest faces
            fewest: dict[str, str] = {}

            for filename in tag.photos:
                image_rel_webpage_url: str = filename.replace(source_dir, '..')+'.html'
                image_rel_thumbnail_url: str = "/thumb/".join(filename.replace(source_dir, '..').rsplit(sep='/', maxsplit=1))
                rec: dict[str, str] = {'webpage': image_rel_webpage_url, 'thumbnail': image_rel_thumbnail_url}
                images.append(rec)

                # save off the first webpage, thumbnail of the cluster for an index page
                photo: Photo | None = self.db.get_photo(filepath=filename)
                if photo is None:
                    continue
                face_count: int = len(photo.faces)
                if face_count < fewest_c:
                    fewest = {'faceid': str(tag.id), 'webpage': str(tag.id)+'.html', 'thumbnail': image_rel_thumbnail_url}
                    fewest_c: int = face_count
            tags_index.append(fewest)
            
            # generate the cluster page using the "faces" template
            html: str | None = templates.render(
                template_type = "faces",
                face_id = tag.id,
                prev = prev_item,
                next = next_item,
                images = images,
                version = "0.0.1"
            )
            if html is None:
                continue
            # lastly, write the html into the cluster page file
            with open(file=faces_dir+f"/{tag.id}.html", mode='w') as fh:
                fh.write(html)  # pyright: ignore[reportUnusedCallResult]
        
        # generate the index page using the "faces" template
        html: str | None = templates.render(
            template_type = "faces_index",
            face_id = "All Faces",
            images = tags_index,
            version = "0.0.1"
        )
        if html is not None:
            # almost lastly, write the html into the cluster index file
            with open(file=faces_dir+"/index.html", mode='w') as fh:
                fh.write(html)

        # backup previous file if it exists
        if os.path.exists(path=faces_dir+"/names.js"):
            date: str = time.strftime("%Y%m%d%H%M%S")
            os.rename(src=faces_dir+"/names.js", dst=faces_dir+f"/names-{date}.js")

        # write a javascript file that can be updated and included to replace face ids with names
        with open(file=faces_dir+"/names.js", mode='w') as fh:
            fh.write("var names = ")  # pyright: ignore[reportUnusedCallResult]
            names: dict[str, str] = {}
            for tag in tags:
                names[str(tag.id)] = str(tag.label)
            json.dump(obj=names, fp=fh, indent=2)
            fh.write(";\n")  # pyright: ignore[reportUnusedCallResult]
