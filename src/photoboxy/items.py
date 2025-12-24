from PIL.ImageFile import ImageFile
from collections.abc import Callable, Generator
from datetime import datetime
from time import struct_time
from typing import Any, override
from shutil import copyfile
import json
import os
from os.path import exists, basename
import time
from subprocess import PIPE, Popen

from PIL import Image as PILImage
from PIL import ImageOps
from PIL.ExifTags import TAGS
from PIL.Image import Exif
#from GPSPhoto import gpsphoto
import piexif

from .template_manager import PhotoboxTemplate
from .photobox_db import BoundingBox, Face, Photo
from .config import Config

# function aliases
def filesize(filename: str) -> int:
    return os.stat(path=filename).st_size

def mtime(filename: str) -> str:
    mt: float = os.stat(path=filename).st_mtime
    ts: struct_time = time.gmtime(mt)
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", ts)

# Directories have
#  * path
#  * mtime
#  * Files[]
#  * Directories[]

# Files have
#  * path
#  * mtime
#  * sort_key (usually mtime or created_time)
#  * Filetype
#  * size

# Filetype is one of
#  * Note
#  * Image
#  * Video

# Notes < File have
#  * type

# Images < File have
#  * created_time (sometimes)
#  * exif_metadata
#  * image_size
#  * format (e.g., jpeg)

# Videos < File have
#  * created_time (sometimes)
#  * video_metadata
#  * video_run_time
#  * format

# to determine if we need to update the thumbnail, file webpage, and/or the index webpage
# if the source mtime is greater than the dest mtime, create thumbnail and file webpage
# if the previous or next file is changed, recreate the file webpage
# if the template was updated, recreate the file webpage
# if files were added, removed, or resorted update the index
# if the template was updated, recreate the index

class FileItem:
    THUMBNAIL_PX: int = 100
    WEBPAGE_PX: int = 800

    def __init__(self, fullpath: str, relpath: str, dest_dir: str, config: Config) -> None:
        self.path: str = fullpath # source path of the original file
        self.relpath: str = relpath # offset from the source root to the source path
        self.dest_dir: str = dest_dir # destination root
        self.config: Config = config
        self.basename: str = basename(p=fullpath)
        self.thumbname: str = self.basename
        self.mtime: str = mtime(filename=fullpath)
        self.date: str = self.mtime.split(sep=' ', maxsplit=1)[0]
        self.sort_key: str = self.mtime # default sort key
        self.size: int = filesize(filename=fullpath)
        self.comment: str | None = None
        self.metadata: dict[str, Any] = {}  # pyright: ignore[reportExplicitAny]
        self.embeddings: list[dict[str, float]] = []
        self.changed: bool = True
        self.htmlonly: bool = False
        self.type: str = 'unknown'
        self.photo: Photo | None = self.config.db.get_photo(filepath=fullpath)
        # check if the item needs to be updated
        if self.photo and self.photo.mtime == self.mtime and self.photo.size == self.size:
            self.metadata = self.photo.metadata
            self.sort_key = self.photo.sort_key
            self.changed = False
        else:
            self.photo = Photo(
                filepath=fullpath,
                mtime=self.mtime,
                size=self.size,
                sort_key=self.sort_key,
                metadata = self.metadata,
                relpath=f"{relpath}/{self.basename}",
                date=self.date,
                faces=[]
            )
            self.changed = True
        # previous item
        self.p: "FileItem | None" = None
        # next item
        self.n: "FileItem | None" = None

    def save(self) -> None:
        if self.photo:
            self.config.db.add_photo(photo=self.photo)

    def do_work(self, cmd: str | Callable[..., None], args: list[str]) -> None:
        self.config.pool.do_work(cmd_or_proc=cmd, args=args)

    @override
    def __str__(self) -> str:
        return self.path
    
    def destname(self, dest_dir: str) -> str:
        return f"{dest_dir}/{self.basename}"
    
    def set_adjacent(self, prev_item: "FileItem | None", next_item: "FileItem | None") -> None:
        self.p = prev_item
        self.n = next_item

    def generate(self, templates: PhotoboxTemplate, dest_dir: str) -> Generator["FileItem | None", None, None]:
        if not self.changed:
            yield
            return
        self.generate_thumbnail(dest_dir)
        self.generate_item(dest_dir)
        self.generate_html(templates, dest_dir)
        yield self

    def generate_thumbnail(self, dest_dir: str) -> None:  # pyright: ignore[reportUnusedParameter]
        pass

    def generate_item(self, dest_dir: str) -> None:  # pyright: ignore[reportUnusedParameter]
        pass

    def generate_html(self, templates: PhotoboxTemplate, dest_dir: str) -> None:
        next_destname: str | None = None
        prev_destname: str | None = None
        if self.n: 
            next_destname= self.n.basename
        if self.p: 
            prev_destname = self.p.basename
        # get the clusters
        if not self.photo:
            return
        # rescale and convert the bounding box to integers, then make it a string with a comma between each coordinate
        tag_data: dict[str, str] = {}
        photo: Photo = self.photo
        if photo.faces:
            r: float = photo.metadata.get('scale', 1.0)
            for face in photo.faces:
                tag_data['bbox'] = f"{face.bbox.left*r},{face.bbox.top*r},{face.bbox.right*r},{face.bbox.bottom*r}"

        # we need to calculate the relative path to the root, remember that the faces directory may not exist yet.
        faces_rel: str = ('../' * self.relpath.count('/'))+'faces'
        # generate the html
        html: str = templates.render(  # pyright: ignore[reportAssignmentType]
            template_type=self.type,
            up='index.html',
            item=self.basename,
            next=next_destname,
            prev=prev_destname,
            metadata=self.metadata,  # pyright: ignore[reportArgumentType]
            faces_rel=faces_rel,
            tags=tag_data,  # pyright: ignore[reportArgumentType]
            comment=self.comment,
            version="0.0.1"
        )
        htmlfile: str = f"{dest_dir}/{self.basename}.html"
        with open(file=htmlfile, mode="w") as fh:
            fh.write(html)  # pyright: ignore[reportUnusedCallResult]

class Image(FileItem):
    def __init__(self, fullpath: str, relpath: str, dest_dir: str, config: Config) -> None:
        FileItem.__init__(self, fullpath=fullpath, relpath=relpath, dest_dir=dest_dir, config=config)
        self.type: str = 'image'
        if self.basename.lower().endswith( ('.tiff', '.svg', '.bmp') ):
            self.thumbname: str = f'{self.basename}.jpg'

        thumbfile: str = f"{dest_dir}/{relpath}/thumb/{self.thumbname}".replace('//', '/')
        if not exists(path=thumbfile):
            self.changed: bool = True
        destfile: str = f"{dest_dir}/{relpath}/{self.basename}"
        if not exists(path=destfile):
            self.changed = True

        if self.changed:
            self.generate_metadata()
            if self.photo:
                self.photo.mtime = self.mtime
                self.photo.size = self.size
                self.photo.sort_key = self.sort_key
                self.photo.metadata = self.metadata
                self.photo.relpath = f"{relpath}/{self.basename}"
                self.photo.date = self.mtime.split(sep=' ',maxsplit=1)[0]
                self.photo.faces = self.embed_faces()
            self.save()

        # we may have all the images created and the metadata is already good, but we are missing the html file
        # recreate it or if the configuration of the updater is set to update the html
        desthtmlfile: str = f"{self.dest_dir}/{relpath}/{self.basename}.html"
        if not exists(path=desthtmlfile) or self.config.htmlonly:
            # set htmlonly only if this is the only reason to set the changed flag
            self.htmlonly: bool = not self.changed
            self.changed = True


    def resize(self, source: str, dest: str, width: int, height: int | None = None, fill: bool = False, gravity: str = 'center') -> None:
        try:
            with PILImage.open(fp=source) as image:
                rotated_image: PILImage.Image | None = ImageOps.exif_transpose(image)
                if rotated_image is None:
                    rotated_image = image.copy()

                if not height: 
                    height = width
                scale: float = 1.0
                if fill:
                    scale = max([ width / image.width, height / image.height ])
                else:
                    scale = min([ width / image.width, height / image.height ])

                resized: PILImage.Image = rotated_image.resize(size=(int(scale * image.width + 0.5), int(scale * image.height + 0.5)))

                if not fill: 
                    resized.save(fp=dest)
                    return

                box: list[float] = []
                if gravity == "top_left":
                    box = [0, 0, width, height]
                elif gravity == "top_right":
                    shift_right: int = resized.width - width
                    box = [shift_right, 0, width + shift_right, height]
                elif gravity == "bottom_left":
                    shift_top: int =  resized.height - height
                    box = [0, shift_top, width, height + shift_top]
                elif gravity == "bottom_right":
                    shift_right: int = resized.width - width
                    shift_top: int =  resized.height - height
                    box = [shift_right, shift_top, shift_right+width, height + shift_top]
                elif gravity == "center":
                    shift_right: int = (resized.width - width) // 2
                    shift_top: int = (resized.height - height) // 2
                    box = [shift_right, shift_top, shift_right+width, height + shift_top]
                if box:
                    cropped: PILImage.Image = resized.crop(box=tuple[float, float, float, float](box))
                    cropped.save(fp=dest)
        except OSError as e:
            print()
            print(f"Error for {self.path}: {e}")

    def resize_background(self, source: str, dest: str, size: int, fill: bool = False) -> None:
        self.do_work(cmd=self.resize, args=[source, dest, size, size, fill])

    @override
    def generate_thumbnail(self, dest_dir: str) -> None:
        if self.htmlonly: return
        imgfile: str = f"{dest_dir}/thumb/{self.thumbname}"
        self.resize_background(source=self.path, dest=imgfile, size=self.THUMBNAIL_PX, fill=True)

    @override
    def generate_item(self, dest_dir: str) -> None:
        if self.htmlonly:
            return
        imgfile: str = f"{dest_dir}/{self.basename}"
        if imgfile.lower().endswith('.svg'):
            try:
                os.link(src=self.path, dst=imgfile)
            except Exception:
                copyfile(src=self.path, dst=imgfile)
        else:
            self.resize(source=self.path, dest=imgfile, width=self.WEBPAGE_PX)
    
    def generate_metadata(self) -> None:
        img: ImageFile = PILImage.open(fp=self.path)
        m: dict[str, Any] = self.metadata  # pyright: ignore[reportExplicitAny]
        m['format'] = img.format
        m['width'] = img.width
        m['height'] = img.height
        m['size'] = os.stat(self.path).st_size
        # keep track of the rescaling ratio so that we can recalculate the bounding boxes
        # that are given by with the clusterer
        m['scale'] = min([ self.WEBPAGE_PX / img.width, self.WEBPAGE_PX / img.height ])
        # generate face embeddings for clustering
        self.embeddings: list[dict[str, float]] = self.config.embedder.embed(image=img)

        exifdata: Exif = img.getexif()
        try:
            piexifdata = piexif.load(self.path, key_is_name=True)
        except Exception:
            piexifdata: dict[str, dict[Any, Any]] = { 'GPS': {}, 'Exif': {} }

        for tag_id in exifdata:
            tag: str | int = TAGS.get(tag_id, tag_id)
            data: Any | None = exifdata.get(tag_id)
            if data is None:
                continue
            try:
                if isinstance(data, bytes):
                    data = data.decode(encoding='utf-8')
                else:
                    data = str(data)
                m[str(tag)] = data

                if str(tag).startswith('DateTime'):
                    datetime_exif: str = data
                    exiftime: str | None = self.parse_exiftime(exif_data=datetime_exif)
                    if exiftime and exiftime < self.sort_key:
                        self.sort_key = exiftime
                        
            except Exception:
                pass

        for tag in piexifdata['Exif']:
            if str(tag).startswith('DateTime'):
                data: Any | None = piexifdata['Exif'][tag]
                if data is None:
                    continue
                if isinstance(data, bytes):
                    data = data.decode(encoding='utf-8')
                else:
                    data = str(data)
                m[str(tag)] = data
                
                exiftime: str | None = self.parse_exiftime(exif_data=data)
                #print(self.path, data, exiftime, self.sort_key)
                if exiftime and exiftime < self.sort_key:
                    self.sort_key = exiftime
                    #print(f"  updated sort_key to {self.sort_key}")
            # try:
            #     gpsdata = gpsphoto.getGPSData(self.path)
            #     if gpsdata and 'Latitude' in gpsdata:
            #         m['gpsdata'] = gpsdata
            # except Exception as e:
            #     #print(f"Exception processing {self.path}: {e}")
            #     pass
    
    def parse_exiftime(self, exif_data: str) -> str | None:
        if exif_data.startswith('0000'):
            return None
        if exif_data.startswith('    '):
            return None
        mdt: str = exif_data.replace(': ', ':0')
        try:
            dt: datetime = datetime.strptime(mdt, '%Y:%m:%d %H:%M:%S')
            ts: str = dt.strftime(format='%Y-%m-%d %H:%M:%S UTC')
            return ts
        except Exception:
            return None

    def embed_faces(self) -> list[Face]:
        img: ImageFile = PILImage.open(fp=self.path)
        embeddings: list[dict[str, list[float]]] = self.config.embedder.embed(image=img)
        faces: list[Face] = []
        for emb in embeddings:
            bbox: BoundingBox = BoundingBox(left=emb["bbox"][0], top=emb["bbox"][1], right=emb["bbox"][2], bottom=emb["bbox"][3])
            vec: list[float] = emb["embed"]
            face: Face = Face(bbox=bbox, embedding=vec, tag_id=None)
            faces.append(face)
        return faces

class Video(FileItem):
    def __init__(self, fullpath: str, relpath: str, dest_dir: str, config: Config) -> None:
        FileItem.__init__(self, fullpath=fullpath, relpath=relpath, dest_dir=dest_dir, config=config)
        self.type: str = 'video'
        self.basename: str = self.basename.rsplit(sep='.', maxsplit=1)[0]+'.webm'
        self.thumbname: str = f"{self.basename}.jpg"
        thumbfile: str = f"{dest_dir}/{relpath}/thumb/{self.thumbname}".replace('//', '/')
        if not exists(path=thumbfile):
            self.changed = True

        destfile: str = f"{dest_dir}/{relpath}/{self.basename}"
        if not exists(path=destfile):
            self.changed = True

        if self.changed:
            with Popen(['/usr/bin/ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', self.path], stdout=PIPE, stderr=None) as p:
                ffprobe_json_raw: bytes = p.stdout.read()

            self.metadata = json.loads(s=ffprobe_json_raw)
            if self.metadata.get('format') is None:
                self.metadata = { 'format': {'format_long_name': 'unknown', 'duration': 'unknown', 'size': 'unknown' }, 'streams': [] }
            
            self.metadata['content_type'] = 'video/webm'
            self.date: str = datetime.now().strftime(format='%Y-%m-%d')
            if self.metadata.get('tags') and self.metadata['tags'].get('creation_time'):
                t = self.metadata['tags'].get('creation_time').split('.',1)[0]
                self.sort_key = t.replace('T', ' ')+" UTC"
                self.date: str = t.split('T', 1)[0]

            if not self.photo:
                return
            self.photo.metadata = self.metadata
            self.save()

        # we may have all the images created and the metadata is already good, but we are missing the html file
        # recreate it
        desthtmlfile: str = f"{self.config.dest_dir}/{relpath}/{self.basename}.html"
        if not exists(path=desthtmlfile):
            # set htmlonly only if this is the only reason to set the changed flag
            self.config.htmlonly = not self.changed
            self.changed = True

    @override
    def generate_thumbnail(self, dest_dir: str) -> None:
        if self.htmlonly: return
        thumbnail_file: str = f"{dest_dir}/thumb/{self.thumbname}"
        cmd: str = f'ffmpeg -i "{self.path}" -hide_banner -loglevel quiet -vcodec mjpeg -vframes 1 -an -f rawvideo -s {self.THUMBNAIL_PX}x{self.THUMBNAIL_PX} -y "{thumbnail_file}"'
        self.do_work(cmd=cmd, args=[])
    
    @override
    def generate_item(self, dest_dir: str) -> None:
        if self.htmlonly: return
        outfile: str = f"{dest_dir}/{self.basename}"
        # (mov|avi|flv|mp4|m4v|mpeg|mpg|webm|ogv)
        cmd: str = f'ffmpeg -i "{self.path}" -hide_banner -loglevel quiet -vcodec libvpx -cpu-used -5 -deadline realtime -y "{outfile}"'
        self.do_work(cmd=cmd, args=[])

class Note(FileItem):
    def __init__(self, fullpath: str, relpath: str, dest_dir: str, config: Config):
        FileItem.__init__(self, fullpath=fullpath, relpath=relpath, dest_dir=dest_dir, config=config)
        self.type = 'note'
        self.thumbname = f"{self.basename}.png"
        thumbfile: str = f"{dest_dir}/thumb/{self.thumbname}".replace('//', '/')

        if not exists(path=thumbfile):
            self.changed = True

        if self.changed:
            with os.popen(cmd=f"file '{self.path}'") as fh:
                self.metadata['magic'] = fh.read().split(sep=': ')[1]
            self.metadata['stat'] = os.stat(self.path)
            if not self.photo:
                return
            self.photo.metadata = self.metadata
            self.save()
            self.image: ImageFile | None = self.convert_into_image()

    def convert_into_image(self) -> ImageFile | None:
        cmd: str = f'unoconv -f pdf --stdout "{self.path}" | convert -background white -[0] PNG8:-'
        p: Popen[bytes] = Popen[bytes](cmd, stdout=PIPE, bufsize=100*1024, shell=True)
        if p.stdout is None:
            return None
        image: ImageFile = PILImage.open(fp=p.stdout)
        return image
    
    @override
    def generate_thumbnail(self, dest_dir: str) -> None:
        outfile: str = f"{dest_dir}/thumb/{self.thumbname}"
        thumb = self.resize(self.image, dest=outfile, width=self.THUMBNAIL_PX, fill=True)

    @override
    def generate_item(self, dest_dir: str) -> None:
        # create a preview
        outfile: str = f"{dest_dir}/{self.thumbname}"
        thumb = self.resize(self.image, dest=outfile, width=self.WEBPAGE_PX)
        # copy the original document over as well
        copyfile(src=self.path, dst=f"{dest_dir}/{self.basename}")
    
    def resize(self, image: ImageFile, dest: str, width: int, height: int | None = None, fill: bool = False, gravity: str = 'center'):
        try:
            image: PILImage.Image | None = ImageOps.exif_transpose(image)
            if image is None:
                return

            if not height: 
                height = width

            if fill:
                scale = max([ width / image.width, height / image.height ])
            else:
                scale = min([ width / image.width, height / image.height ])

            resized: PILImage.Image = image.resize(size=(int(scale * image.width + 0.5), int(scale * image.height + 0.5)))

            if not fill: 
                resized.save(fp=dest)
                return
            box: list[float] = [0, 0, width, height]
            if gravity == "top_left":
                box = [0, 0, width, height]
            elif gravity == "top_right":
                shift_right = resized.width - width
                box = [shift_right, 0, width + shift_right, height]
            elif gravity == "bottom_left":
                shift_top =  resized.height - height
                box = [0, shift_top, width, height + shift_top]
            elif gravity == "bottom_right":
                shift_right = resized.width - width
                shift_top =  resized.height - height
                box = [shift_right, shift_top, shift_right+width, height + shift_top]
            elif gravity == "center":
                shift_right = (resized.width - width) // 2
                shift_top = (resized.height - height) // 2
                box = [shift_right, shift_top, shift_right+width, height + shift_top]
            tuple_box: tuple[float, float, float, float] = tuple[float, float, float, float](box)
            cropped: PILImage.Image = resized.crop(box=tuple_box)
            cropped.save(fp=dest)
        except OSError as e:
            print()
            print(f"Error for {self.path}: {e}")
