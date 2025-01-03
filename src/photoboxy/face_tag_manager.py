import time
import os
import glob
import json
from shutil import copyfile

class FaceTagManager:
    def __init__(self, db):
        self.db = db
        self.faces = db.get('.faces', {})
        self.names = db.get('.names', {})
        # rebuild the files to tags database
        self.files = {}
        for filename in db:
            if filename.startswith("."): continue
            if 'tags' not in db[filename]: continue
            self.files[filename] = db[filename]['tags']

    def save(self):
        self.db['.faces'] = self.faces
        self.db['.names'] = self.names
        for filename in self.files:
            self.db[filename]['tags'] = self.files[filename]

    def get_tags(self, filename: str) -> list:
        return self.files.get(filename, [])
    
    def in_bbox(self, bbox: list[float], x: float, y: float) -> bool:
        if x < bbox[0]: return False
        if y < bbox[1]: return False
        if x > bbox[2]: return False
        if y > bbox[3]: return False
        return True
    
    # retagging a
    def retag(self, filename: str, old_face_id: int, new_face_id: int, x: int=None, y: int=None):
        """Retagging a tag means to change the face_id associated with a given (or multiple) bounding boxes

        Args:
            filename (str): source filename of the photo
            old_face_id (int): the current face_id to search for and replace
            new_face_id (int): the new face_id to use for matching tags
            x (int, optional): if specified, it limits the replacement to just the tags that the bounding box contains the x,y. Defaults to None.
            y (int, optional): if specified, it limits the replacement to just the tags that the bounding box contains the x,y. Defaults to None.

        Returns:
            _type_: None
        """
        new_name = self.names.get(new_face_id, new_face_id)
        found = False
        for face in self.files[filename]:
            # if coordinates are specified, check if they are in the bounding box
            if x and y:
                if not self.in_bbox(face['bbox'], x, y): continue
            if face['face_id'] == old_face_id:
                face['face_id'] = new_face_id
                face['name'] = new_name
                found = True
                if filename not in self.faces[new_face_id]:
                    self.faces[new_face_id].append(filename)
        
        if found:
            if old_face_id not in [face['face_id'] for face in self.files[filename]]:
                self.faces[old_face_id].remove(filename)
            new_file_id = len(self.faces[new_face_id]) - 1
            return new_file_id
        return None

    def add_new_facename(self, name: str) -> int:
        face_id = max([x for x in self.faces.keys()]) + 1
        self.names[face_id] = name
        self.faces[face_id] = []
        return face_id

    def rename_faceid(self, face_id: int, name: str):
        """This changes the name associated with the face_id, updating all tags using that face_id"""
        self.names[face_id] = name

    def tag_face(self, filename: str, bbox: list[float], face_id: int):
        """record the association of a bbox in a filename to a face_id"""
        
        # to generate the cluster pages, you need a list of files per cluster
        if filename not in self.faces[face_id]:
            self.faces[face_id].append(filename)
        # to generate the click targets on the image page, you need a way to
        # query the clusterer if it has clusters and bounding boxes for that image
        # using get_clusters(...)
        self.files[filename].append( {'face_id': face_id, 'bbox': bbox} )

    def remove_tag(self, filename: str, face_id: int, x: int=None, y: int=None):
        """ This removes the association of one or more face_id tags from a photo 
        if coordinates x and y are given, then it will limit it to just that one tagging """
        if filename not in self.files: return
        tags = self.files[filename]
        tags_to_keep = []
        for tag in tags:
            # if you provided a coordinate, and the coordinate is inside the bbox, and the face_id matches, exclude it 
            if x and y:
                if tag['face_id'] == face_id and self.in_bbox(tag['bbox'], x, y):
                    # remove one instance of the filename from the face_id to filenames list
                    if filename in self.faces[face_id]:
                        self.faces[face_id].remove(filename)
                else:
                    tags_to_keep.append(tag)
            else:
                # if there was no coordinate, and the face_id matches, exclude it
                if tag['face_id'] == face_id:
                    # remove one instance of the filename from the face_id to filenames list
                    if filename in self.faces[face_id]:
                        self.faces[face_id].remove(filename)
                else:
                    tags_to_keep.append(tag)
        self.files[filename] = tags_to_keep

    def remove_all_tags_for_face(self, face_id: int):
        """ Remove all tags for a face_id and then remove the record for the face_id
         this removes that face completely from the index """
        if face_id not in self.faces:
            return
        files = self.faces[face_id]
        for f in files:
            self.remove_tag(f, face_id)
        self.faces.pop(face_id)
        self.names.pop(face_id)

    def generate(self, templates, dest_dir, source_dir):
        # 1st, make the destination directories
        faces_dir = dest_dir+'/faces'
        res_dir = faces_dir+'/res'
        os.makedirs(res_dir, exist_ok=True)
        # 2nd, remove previous cluster pages since the clusters may be different and not use all the same
        # cluster numbers as previous runs
        for fn in glob.glob(faces_dir+'*.html'):
            os.unlink(faces_dir+fn)

        # 3th, copy over the resources
        # for each resource, copy it over
        for f in os.scandir(templates['res']):
            item = f.name
            copyfile(f"{templates['res']}/{item}", f"{res_dir}/{item}")

        # 4th, sort the clusters by length, longest first
        faces_order = sorted(self.faces.keys(), key=lambda c: len(self.faces[c]), reverse=True)

        # 4th and a half, create a list for the index page to keep the first image thumbname and webpage for each cluster
        faces_index = []

        # 5th, enumerate through the order cluster names, so that we can determine next and previous clusters for the template
        for index, face_id in enumerate(faces_order):
            # determine the next and previous clusters
            prev = next_item = None
            if index > 0:
                prev = faces_order[index - 1]
            if index < len(faces_order) - 1:
                next_item = faces_order[index + 1]
            
            # 6th, wrap the webpage and thumbnail urls into a list of dictionaries for the template
            # this is tricky
            images = []
            fewest_c = 10000 # used to add the photo with the fewest faces
            fewest = None
            for filename in self.faces[face_id]:
                image_rel_webpage_url = filename.replace(source_dir, '..')+'.html'
                image_rel_thumbnail_url = "/thumb/".join(filename.replace(source_dir, '..').rsplit('/', 1))
                rec = {'webpage': image_rel_webpage_url, 'thumbnail': image_rel_thumbnail_url}
                images.append(rec)
                # save off the first webpage, thumbnail of the cluster for an index page
                if len(self.files[filename]) < fewest_c:
                    fewest = {'faceid': str(face_id), 'webpage': str(face_id)+'.html', 'thumbnail': image_rel_thumbnail_url}
                    fewest_c = len(self.files[filename])
            faces_index.append(fewest)
            
            # generate the cluster page using the "faces" template
            html = templates["faces"].render(
                face_id = face_id,
                prev = prev,
                next = next_item,
                images = images,
                version = "0.0.1"
            )

            # lastly, write the html into the cluster page file
            with open(faces_dir+f"/{face_id}.html", 'w') as fh:
                fh.write(html)
        
        # generate the index page using the "faces" template
        html = templates["faces_index"].render(
            face_id = "All Faces",
            images = faces_index,
            version = "0.0.1"
        )

        # almost lastly, write the html into the cluster index file
        with open(faces_dir+"/index.html", 'w') as fh:
            fh.write(html)

        # backup previous file if it exists
        if os.path.exists(faces_dir+"/names.js"):
            date = time.strftime("%Y%m%d%H%M%S")
            os.rename(faces_dir+"/names.js", faces_dir+f"/names-{date}.js")

        # write a javascript file that can be updated and included to replace face ids with names
        with open(faces_dir+"/names.js", 'w') as fh:
            fh.write("var names = ")
            names = {}
            for face_id in faces_order:
                names[face_id] = self.names.get(face_id, str(face_id))
            json.dump(names, fh, indent=2)
            fh.write(";\n")
