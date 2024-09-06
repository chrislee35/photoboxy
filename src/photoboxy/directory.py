import json
import os
import shutil
# function aliases
exists = os.path.exists
basename = os.path.basename
dirname = os.path.dirname
mtime = lambda filename: os.stat(filename).st_mtime
from shutil import copyfile
from .photoboxy import VERSION
from .items import Image, Video, Note

def rreplace(string: str, find: str, replacement: str, count: int = 1):
    return replacement.join(string.rsplit(find, count))

class Directory:
    excludes = ( 'albumfiles.txt', 'comments.properties', 'meta.properties', 'photoboxy.dbm', 'photoboxy.dbm.pag', 'photoboxy.dbm.dir' )

    def __init__(self, fullpath, relpath='', updater: any = None):
        self.path = fullpath
        self.relpath = relpath
        self.updater = updater
        self.basename = basename(fullpath)
        self.mtime = mtime(fullpath)
        self.type = 'folder'
        self.image = "res/album.png"
        self.files = []
        self.subdirs = []
        self.changed = True

    def enumerate(self, updater):
        comments = {}
        if exists(f"{self.path}/comments.properties"):
            try:
                comments = self._parse_comments(f"{self.path}/comments.properties")
            except Exception as e:
                print(e)
                raise Exception(f"Could not process {self.path}/comments.properties")
        
        # check for excludes
        exclude = set()
        if exists(f"{self.path}/albumfiles.txt"):
            with open(f"{self.path}/albumfiles.txt", 'r') as fh:
                for l in fh.readlines():
                    if l.startswith('-'):
                        fn = l.split('\t')[0][1:]
                        exclude.add(fn)


        # check for other reasons to update
        if not exists(f"{updater.dest_dir}/{self.relpath}/index.html"):
            self.changed = True

        video_exts = ('.mov', '.avi', '.flv', '.mp4', '.mpeg', '.mpg', '.webm', '.ogg')
        photo_exts = ('.jpg', '.gif', '.jpeg', '.png', '.tif', '.tiff', '.svg', '.bmp')
        doc_exts = ('.txt', '.rtf', '.doc', '.docx', '.pdf')

        for f in os.scandir(self.path):
            if f.name in exclude: continue
            if f.name in Directory.excludes: continue
            if f.name.startswith('.'): continue
            
            item_path = f"{self.path}/{f.name}"
            if f.is_dir():
                updater._add_total('folder')
                newdir = Directory(item_path, f"{self.relpath}{f.name}/", updater)
                self.subdirs.append(newdir)
                newdir.enumerate(updater)
                if newdir.changed:
                    self.changed = True

            elif f.name.lower().endswith(photo_exts):
                updater._add_total('image')
                newfile = Image(item_path, self.relpath, updater)
                self.files.append(newfile)
                if newfile.changed:
                    self.changed = True
                    updater._add_change('image', newfile)

            elif f.name.lower().endswith(video_exts):
                updater._add_total('video')
                newfile = Video(item_path, self.relpath, updater)
                self.files.append(newfile)
                if newfile.changed:
                    self.changed = True
                    updater._add_change('video', newfile)

            elif f.name.lower().endswith(doc_exts):
                updater._add_total('note')
                newfile = Note(item_path, self.relpath, updater)
                self.files.append(newfile)
                if newfile.changed:
                    self.changed = True
                    updater._add_change('note', newfile)

            else:
                updater._add_skip()

        self.select_folder_image()

        if self.changed:
            updater._add_change('folder', self)

    def _parse_comments(self, filename) -> dict[str, str]:
        comments = {}
        prevkey = None
        with open(f"{self.path}/comments.properties") as fh:
            for l in fh.readlines():
                l = l.strip()
                newline = False
                if l.endswith('\\'):
                    newline = True
                    l = rreplace(l, '\\', '\n')
                
                if prevkey:
                    comments[prevkey] += l
                    if not newline:
                        prevkey = None
                else:
                    key, comment = l.split('=', 1)
                    comments[key] = comment
                    if newline:
                        prevkey = key
        return comments
    
    def select_folder_image(self) -> str:
        self.image = "res/album.png"
        # next, let's find the icon image for this folder
        # do I have one defined by configuration?
        if exists(f"{self.path}/meta.properties"):
            with open(f"{self.path}/meta.properties", 'r') as fh:
                for l in fh.readlines():
                    if l.startswith('folderIcon='):
                        thumbnail = l.strip().split('=',1)[1]
                        if thumbnail.lower().endswith('.jpg'):
                            self.image = f"thumb/{thumbnail}"
                            return self.image
                        else:
                            for subdir in self.subdirs:
                                if subdir.image and subdir.basename == thumbnail:
                                    self.image = subdir.basename+'/'+subdir.image
                                    return self.image
        
        # do I have any images?    If so, I'll pick the first one. (it's gotta be the best one, right?)
        if len(self.files) > 0:
            self.image = "thumb/"+self.files[0].thumbname
                
        for subdir in self.subdirs:
            if subdir.image:
                self.image = subdir.basename+'/'+subdir.image
                return self.image
        return self.image
    
    def generate(self, templates: dict, dest_dir: str):
        if not self.changed: return

        self.subdirs.sort(key=lambda x: x.basename)
        self.files.sort(key=lambda x: x.sort_key)

        # set up the next and previous for all the items
        if len(self.files) > 1:
            self.files[0].n = self.files[1]
            self.files[-1].p = self.files[-2]
        for i in range(1, len(self.files) - 1):
            self.files[i].set_adjacent(self.files[i-1], self.files[i+1])

        # let's first check if the output directory exists (added thumb to make sure it's created too)
        if not exists(f"{dest_dir}/thumb"):
            # we need to create the directory
            os.makedirs(f"{dest_dir}/thumb")

        # next, let's check if the resources are all copied over, first create the res dir
        if not exists(f"{dest_dir}/res"):
            # we need to create the res folder
            os.makedirs(f"{dest_dir}/res")

        # for each resource, copy it over if it's newer
        for f in os.scandir(templates['res']):
            item = f.name
            if not exists(f"{dest_dir}/res/{item}") or mtime(f"{templates['res']}/{item}") > mtime(f"{dest_dir}/res/{item}"):
                copyfile(f"{templates['res']}/{item}", f"{dest_dir}/res/{item}")

        # then we need to (re)create the index.html
        # first, calculate all the parent folder links
        parts = self.relpath.rstrip('/').split("/")
        if len(parts) == 0:
            parents = [ {'folder': 'Home', 'link': "javascript:void(0)", 'disabled': True} ]
        else:
            parents = \
                [
                    {'folder': 'Home', 'link': ("../" * len(parts)) + "index.html", 'disabled': False}
                ] + [
                    {'folder': folder, 'link': ("../" * (len(parts) - (index + 1))) + "index.html", 'disabled': False} 
                    for index, folder in enumerate(parts)
                ]
            parents[-1]['link'] = "javascript:void(0)"
            parents[-1]['disabled'] = True
        
        html = templates[self.type].render(item=self.relpath, parents=parents, subdirs=self.subdirs, files=self.files, version=VERSION)
        with open(f"{dest_dir}/index.html", "w") as of:
            of.write(html)

        self.generate_shuffle(templates, dest_dir)
        self.updater._add_generated('folder')

        for f in self.files:
            f.generate(templates, dest_dir)

        for s in self.subdirs:
            s.generate(templates, f"{dest_dir}/{s.basename}")


    def update_template(self, templates: dict, dest_dir: str):
        self.subdirs.sort(key=lambda x: x.basename)
        self.files.sort(key=lambda x: x.sort_key)

        # set up the next and previous for all the items
        if len(self.files) > 1:
            self.files[0].set_adjacent(None, self.files[1])
            self.files[-1].set_adjacent(self.files[2], None)
        for i in range(1, len(self.files) - 1):
            self.files[i].set_adjacent(self.files[i-1], self.files[i+1])
        # let's first check if the output directory exists (added thumb to make sure it's created too)
        if not exists(f"{dest_dir}/thumb"):
            # we need to create the directory
            os.makedirs(f"{dest_dir}/thumb")

        # next, let's check if the resources are all copied over, first create the res dir
        if not exists(f"{dest_dir}/res"):
            # we need to create the res folder
            os.makedirs(f"{dest_dir}/res")

        # for each resource, copy it over if it's newer
        for f in os.scandir(templates['res']):
            item = f.name
            if not exists(f"{dest_dir}/res/{item}") or mtime(f"{templates['res']}/{item}") > mtime(f"{dest_dir}/res/{item}"):
                copyfile(f"{templates['res']}/{item}", f"{dest_dir}/res/{item}")

        # then we need to (re)create the index.html
        # first, calculate all the parent folder links
        parts = self.rel.split("/")
        parents = \
            [
                {'folder': 'Home', 'link': ("../" * len(parts)) + "index.html"}
            ] + [
                {'folder': folder, 'link': ("../" * (len(parts) - index - 1)) + "index.html" } 
                for index, folder in enumerate(parts[0:-1])
            ]
        html = templates[self.type].render(item=self.rel, parents=parents, subdirs=self.subdirs, files=self.files, version=VERSION)
        with open(f"{dest_dir}/index.html", "w") as of:
            of.write(html)

        for s in self.subdirs:
            s.update_template(templates, f"{dest_dir}/{s.basename}")

    def generate_shuffle(self, templates: dict, dest_dir: str):
        # enumerate all the images in this folder and below
        images = self.get_images_recursive()
        # get the relpath, date, and folder for each image
        rpl = len(self.relpath)
        image_array = []
        for image in images:
            relpath = (image.relpath[rpl:].strip('/')+'/'+image.basename).strip('/')
            folder = os.path.dirname(relpath)
            date = image.mtime.split(' ')[0]
            image_array.append({'path': relpath, 'folder': folder, 'date': date})

        image_array_str = json.dumps(image_array)
        html = templates['shuffle'].render(image_array=image_array_str, version=VERSION)
        with open(f"{dest_dir}/shuffle.html", "w") as of:
            of.write(html)

    def get_images_recursive(self):
        images = [img for img in self.files if isinstance(img, Image)]
        for s in self.subdirs:
            images += s.get_images_recursive()
        return images
