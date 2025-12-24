from photoboxy.config import Config


import json
import os
from os.path import exists, basename
from jinja2 import Template
from shutil import copyfile

from .template_manager import PhotoboxTemplate
from .items import FileItem, Image, Video, Note
#from .updater import Updater
from .config import Config
from collections.abc import Generator

def mtime (filename: str) -> float:
    return os.stat(path=filename).st_mtime

def rreplace(string: str, find: str, replacement: str, count: int = 1) -> str:
    return replacement.join(string.rsplit(sep=find, maxsplit=count))


class Directory:
    excludes: set[str] = { 'albumfiles.txt', 'comments.properties', 'meta.properties' }

    def __init__(self, fullpath: str, relpath: str, config: Config) -> None:
        self.path: str = fullpath
        self.relpath: str = relpath
        self.config: Config = config
        self.dest_path: str = os.path.join(config.dest_dir, relpath)
        self.basename: str = basename(p=fullpath)
        self.mtime: float = mtime(filename=fullpath)
        self.comment: str | None = None
        self.type: str = 'folder'
        self.image: str = "res/album.png"
        self.files: list[FileItem] = []
        self.subdirs: "list[Directory]" = []
        self.changed: bool = False

    def enumerate(self) -> Generator["Directory | FileItem | None", None, None]:
        comments: dict[str, str] = {}
        if exists(path=f"{self.path}/comments.properties"):
            try:
                comments = self._parse_comments(filename=f"{self.path}/comments.properties")
            except Exception as e:
                print(e)
                raise Exception(f"Could not process {self.path}/comments.properties")
        
        # check for excludes
        exclude: set[str] = set[str]()
        if exists(path=f"{self.path}/albumfiles.txt"):
            with open(file=f"{self.path}/albumfiles.txt", mode='r') as fh:
                for l in fh.readlines():
                    if l.startswith('-'):
                        fn: str = l.split(sep='\t')[0][1:]
                        exclude.add(fn)


        # check for other reasons to update
        if not exists(path=f"{self.config.dest_dir}/{self.relpath}/index.html"):
            self.changed = True

        video_exts: tuple[str, ...] = ('.mov', '.avi', '.flv', '.mp4', '.mpeg', '.mpg', '.webm', '.ogg')
        photo_exts: tuple[str, ...] = ('.jpg', '.gif', '.jpeg', '.png', '.tif', '.tiff', '.svg', '.bmp')
        doc_exts:   tuple[str, ...] = ('.txt', '.doc', '.docx', '.pdf', '.odt')

        for f in os.scandir(self.path):
            if f.name in exclude:
                continue
            if f.name in Directory.excludes:
                continue
            if f.name.startswith('.'):
                continue
            
            item_path: str = f"{self.path}/{f.name}"
            if f.is_dir():
                newdir: Directory = Directory(fullpath=item_path, relpath=f"{self.relpath}{f.name}/", config=self.config)
                self.subdirs.append(newdir)
                newdir.comment = comments.get(f.name)
                yield from newdir.enumerate()
                if newdir.changed:
                    self.changed = True
                yield newdir

            elif f.name.lower().endswith(photo_exts):
                newfile: FileItem = Image(fullpath=item_path, relpath=self.relpath, dest_dir=self.dest_path, config=self.config)
                self.files.append(newfile)
                newfile.comment = comments.get(f.name)
                if newfile.changed:
                    self.changed = True
                yield newfile

            elif f.name.lower().endswith(video_exts):
                if self.config.skip_videos:
                    yield None
                    continue
                newfile: FileItem = Video(fullpath=item_path, relpath=self.relpath, dest_dir=self.dest_path, config=self.config)
                self.files.append(newfile)
                newfile.comment = comments.get(f.name)
                if newfile.changed:
                    self.changed = True
                yield newfile

            elif f.name.lower().endswith(doc_exts):
                if self.config.skip_docs:
                    yield None
                    continue
                newfile: FileItem = Note(fullpath=item_path, relpath=self.relpath, dest_dir=self.dest_path, config=self.config)
                self.files.append(newfile)
                newfile.comment = comments.get(f.name)
                if newfile.changed:
                    self.changed = True
                yield newfile
            else:
                yield None

        self.select_folder_image()
        yield self

    def _parse_comments(self, filename: str) -> dict[str, str]:
        comments: dict[str, str] = {}
        prevkey: str | None = None
        with open(file=filename) as fh:
            for l in fh.readlines():
                l: str = l.strip()
                newline = False
                if l.endswith('\\'):
                    newline = True
                    l: str = rreplace(string=l, find='\\', replacement='\n')
                
                if prevkey:
                    comments[prevkey] += l
                    if not newline:
                        prevkey = None
                else:
                    key, comment = l.split(sep='=', maxsplit=1)
                    comments[key] = comment
                    if newline:
                        prevkey = key
        return comments
    
    def select_folder_image(self) -> None:
        self.image = "res/album.png"
        # next, let's find the icon image for this folder
        # do I have one defined by configuration?
        if exists(path=f"{self.path}/meta.properties"):
            with open(file=f"{self.path}/meta.properties", mode='r') as fh:
                for l in fh.readlines():
                    if l.startswith('folderIcon='):
                        thumbnail: str = l.strip().split(sep='=',maxsplit=1)[1]
                        if thumbnail.lower().endswith('.jpg'):
                            self.image = f"thumb/{thumbnail}"
                            return
                        else:
                            for subdir in self.subdirs:
                                if subdir.image and subdir.basename == thumbnail:
                                    self.image = subdir.basename+'/'+subdir.image
                                    return
        
        # do I have any images?    If so, I'll pick the first one. (it's gotta be the best one, right?)
        if len(self.files) > 0:
            self.image = "thumb/"+self.files[0].thumbname
                
        for subdir in self.subdirs:
            if subdir.image:
                self.image = subdir.basename+'/'+subdir.image
                return
    
    def generate(self, templates: PhotoboxTemplate, dest_dir: str) -> Generator["FileItem | Directory | None", None, None]:
        if not self.changed:
            yield
            return
        
        self.subdirs.sort(key=lambda x: x.basename)
        self.files.sort(key=lambda x: x.sort_key)

        # set up the next and previous for all the items
        if len(self.files) > 1:
            self.files[0].n = self.files[1]
            self.files[-1].p = self.files[-2]
        for i in range(1, len(self.files) - 1):
            self.files[i].set_adjacent(prev_item=self.files[i-1], next_item=self.files[i+1])

        # let's first check if the output directory exists (added thumb to make sure it's created too)
        if not exists(path=f"{dest_dir}/thumb"):
            # we need to create the directory
            os.makedirs(name=f"{dest_dir}/thumb")

        # next, let's check if the resources are all copied over, first create the res dir
        if not exists(path=f"{dest_dir}/res"):
            # we need to create the res folder
            os.makedirs(name=f"{dest_dir}/res")

        # for each resource, copy it over if it's newer
        res_template: str = templates.res
        for f in os.scandir(path=res_template):
            item: str = f.name
            if not exists(path=f"{dest_dir}/res/{item}") or mtime(filename=f"{templates.res}/{item}") > mtime(filename=f"{dest_dir}/res/{item}"):
                copyfile(src=f"{templates.res}/{item}", dst=f"{dest_dir}/res/{item}")  # pyright: ignore[reportUnusedCallResult]

        # then we need to (re)create the index.html
        # first, calculate all the parent folder links 
        parts: list[str] = self.relpath.rstrip('/').split(sep="/")
        if len(parts) == 0:
            parents: list[dict[str, str | bool]] = [ {'folder': 'Home', 'link': "javascript:void(0)", 'disabled': True} ]
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

        html: str = templates.render(  # pyright: ignore[reportAssignmentType]
            template_type=self.type,
            item=self.relpath,
            parents=parents,  # pyright: ignore[reportArgumentType]
            subdirs=self.subdirs,  # pyright: ignore[reportArgumentType]
            files=self.files,  # pyright: ignore[reportArgumentType]
            comment=self.comment,
            version="0.0.1"
        )
        with open(file=f"{dest_dir}/index.html", mode="w") as of:
            of.write(html)  # pyright: ignore[reportUnusedCallResult]

        self.generate_shuffle(templates, dest_dir)
        #self.updater._add_generated(type='folder')  # pyright: ignore[reportPrivateUsage]

        for f in self.files:
            yield from f.generate(templates, dest_dir)

        for s in self.subdirs:
            yield from s.generate(templates, dest_dir=f"{dest_dir}/{s.basename}")
        
        yield self


    def update_template(self, templates: PhotoboxTemplate, dest_dir: str) -> None:
        self.subdirs.sort(key=lambda x: x.basename)
        self.files.sort(key=lambda x: x.sort_key)

        # set up the next and previous for all the items
        if len(self.files) > 1:
            self.files[0].set_adjacent(prev_item=None, next_item=self.files[1])
            self.files[-1].set_adjacent(prev_item=self.files[2], next_item=None)
        for i in range(1, len(self.files) - 1):
            self.files[i].set_adjacent(prev_item=self.files[i-1], next_item=self.files[i+1])
        # let's first check if the output directory exists (added thumb to make sure it's created too)
        if not exists(path=f"{dest_dir}/thumb"):
            # we need to create the directory
            os.makedirs(name=f"{dest_dir}/thumb")

        # next, let's check if the resources are all copied over, first create the res dir
        if not exists(path=f"{dest_dir}/res"):
            # we need to create the res folder
            os.makedirs(name=f"{dest_dir}/res")

        # for each resource, copy it over if it's newer
        res_dir: str = templates.res
        for f in os.scandir(res_dir):
            item: str = f.name
            if not exists(path=f"{dest_dir}/res/{item}") or mtime(filename=f"{templates.res}/{item}") > mtime(filename=f"{dest_dir}/res/{item}"):
                copyfile(src=f"{templates.res}/{item}", dst=f"{dest_dir}/res/{item}")  # pyright: ignore[reportUnusedCallResult]

        # then we need to (re)create the index.html
        # first, calculate all the parent folder links
        parts: list[str] = self.relpath.split(sep="/")
        parents: list[dict[str, str]] = \
            [
                {'folder': 'Home', 'link': ("../" * len(parts)) + "index.html"}
            ] + [
                {'folder': folder, 'link': ("../" * (len(parts) - index - 1)) + "index.html" } 
                for index, folder in enumerate[str](parts[0:-1])
            ]
        html: str = templates.render(  # pyright: ignore[reportAssignmentType]
            template_type=self.type, 
            item=self.relpath, 
            parents=parents,   # pyright: ignore[reportArgumentType]
            subdirs=self.subdirs,   # pyright: ignore[reportArgumentType]
            files=self.files,   # pyright: ignore[reportArgumentType]
            comment=self.comment, 
            version="0.0.1"
        )
        with open(file=f"{dest_dir}/index.html", mode="w") as of:
            of.write(html)  # pyright: ignore[reportUnusedCallResult]

        for s in self.subdirs:
            s.update_template(templates, dest_dir=f"{dest_dir}/{s.basename}")

    def generate_shuffle(self, templates: PhotoboxTemplate, dest_dir: str) -> None:
        # enumerate all the images in this folder and below
        images: list[Image] = self.get_images_recursive()
        # get the relpath, date, and folder for each image
        rpl = len(self.relpath)
        image_array: list[dict[str, str]] = []
        for image in images:
            relpath: str = (image.relpath[rpl:].strip('/')+'/'+image.basename).strip('/')
            folder: str = os.path.dirname(relpath)
            date: str = image.mtime.split(sep=' ')[0]
            image_array.append({'path': relpath, 'folder': folder, 'date': date})

        image_array_str: str = json.dumps(obj=image_array)
        template: Template = templates.shuffle
        html: str = template.render(image_array=image_array_str, version="0.0.1")
        with open(file=f"{dest_dir}/shuffle.html", mode="w") as of:
            of.write(html)  # pyright: ignore[reportUnusedCallResult]

    def get_images_recursive(self) -> list[Image]:
        images: list[Image] = [img for img in self.files if isinstance(img, Image)]
        for s in self.subdirs:
            images += s.get_images_recursive()
        return images

