from .photoboxy import VERSION
from .pool import Pool

from PIL import Image as PILImage
from PIL.ExifTags import TAGS
from shutil import copyfile

import json
import os
import time
# function aliases
exists = os.path.exists
basename = os.path.basename
dirname = os.path.dirname
filesize  = lambda filename: os.stat(filename).st_size

def mtime(filename: str) -> str:
    mt = os.stat(filename).st_mtime
    ts = time.gmtime(mt)
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", ts)

class FileItem:
    def __init__(self, fullpath: str, relpath: str, updater: object):
        self.path = fullpath
        self.relpath = relpath
        self.updater = updater
        self.basename = basename(fullpath)
        self.thumbname = self.basename
        self.mtime = mtime(fullpath)
        self.sort_key = self.mtime # default sort key
        self.size = filesize(fullpath)
        self.metadata = {}
        self.changed = True
        self.type = 'unknown'
        data = updater.get_data(fullpath)
        if data and data['mtime'] == self.mtime and data['size'] == self.size:
            self.metadata = data['metadata']
            self.sort_key = data['sort_key']
            self.changed = False
        self.p = self.n = None

    def __str__(self) -> str:
        return self.path
    
    def destname(self, dest_dir: str) -> str:
        return f"{dest_dir}/{self.basename}"
    
    def set_adjacent(self, prev_item, next_item):
        self.p = prev_item
        self.n = next_item

    def generate(self, templates: dict, dest_dir: str):
        if not self.changed: return
        self.generate_thumbnail(dest_dir)
        self.generate_item(dest_dir)
        self.generate_html(templates, dest_dir)
        self.updater._add_generated(self.type)

    def generate_thumbnail(self, dest_dir: str):
        pass

    def generate_item(self, dest_dir: str):
        pass

    def generate_html(self, templates: dict, dest_dir: str):
        template = templates[self.type]
        next_destname = None
        prev_destname = None
        if self.n: next_destname = self.n.basename
        if self.p: prev_destname = self.p.basename
        html = template.render(up='index.html', item=self.basename, next=next_destname, prev=prev_destname, metadata=self.metadata, version=VERSION)
        htmlfile = f"{dest_dir}/{self.basename}.html"
        with open(htmlfile, "w") as fh:
            fh.write(html)

    def wait(self):
        self.updater.wait()

    def myfork(self, func):
        if isinstance(func, str):
            self.updater.fork_cmd(func)
        else:
            self.updater.fork_proc(func)

class Image(FileItem):
    def __init__(self, fullpath: str, relpath: str, updater: object):
        FileItem.__init__(self, fullpath, relpath, updater)
        self.type = 'image'
        if self.basename.lower().endswith( ('.tiff', '.svg', '.bmp') ):
            self.thumbname = f'{self.basename}.jpg'

        thumbfile = f"{updater.dest_dir}/{relpath}/thumb/{self.thumbname}".replace('//', '/')
        if not exists(thumbfile):
            self.changed = True
        
        if self.changed:
            self.generate_metadata()
            data = {
                'mtime': self.mtime,
                'size': self.size,
                'sort_key': self.sort_key,
                'metadata': self.metadata
            }
            updater.set_data(fullpath, data)


    def resize(self, source: str, dest: str, width: int, height: int = None, fill: bool = False, gravity = 'center'):
        image = PILImage.open(source)
        if not height: height = width
        if fill:
            scale = max([ width / image.width, height / image.height ])
        else:
            scale = min([ width / image.width, height / image.height ])

        resized = image.resize(size=(int(scale * image.width + 0.5), int(scale * image.height + 0.5)))
        
        if not fill: 
            resized.save(dest)
            return

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
        cropped = resized.crop(box=box)
        cropped.save(dest)

    def resize_background(self, source: str, dest: str, size: int, fill: bool = False):
        self.updater.fork_proc(self.resize, (source, dest, size, size, fill))

    def generate_thumbnail(self, dest_dir: str):
        imgfile = f"{dest_dir}/thumb/{self.thumbname}"
        self.resize_background(self.path, imgfile, 100, fill=True)

    def generate_item(self, dest_dir):
        imgfile = f"{dest_dir}/{self.basename}"
        if imgfile.lower().endswith('.svg'):
            try:
                os.link(self.path, imgfile)
            except Exception:
                copyfile(self.path, imgfile)
        else:
            self.resize(self.path, imgfile, 800)
    
    def generate_metadata(self):
        img = PILImage.open(self.path)
        m = self.metadata
        m['format'] = img.format
        m['width'] = img.width
        m['height'] = img.height
        m['size'] = os.stat(self.path).st_size

        exifdata = img.getexif()
        for tag_id in exifdata:
            tag = TAGS.get(tag_id, tag_id)
            data = exifdata.get(tag_id)
            try:
                if isinstance(data, bytes):
                    data = data.decode('utf-8')
                else:
                    data = str(data)
                m[tag] = data
            except Exception:
                pass

class Video(FileItem):
    def __init__(self, fullpath: str, relpath: str, updater: object):
        FileItem.__init__(self, fullpath, relpath, updater)
        self.type = 'video'
        self.thumbname = f"{self.basename}.jpg"
        thumbfile = f"{updater.dest_dir}/{relpath}/thumb/{self.thumbname}".replace('//', '/')
        if not exists(thumbfile):
            self.changed = True
        if self.changed:
            with os.popen(f'ffprobe -v error -show_format -show_streams -of json "{self.path}"') as fh:
                ffprobe_json_raw = fh.read()
            self.metadata = json.loads(ffprobe_json_raw)
            if self.metadata.get('format') is None:
                self.metadata = { 'format': {'format_long_name': 'unknown', 'duration': 'unknown', 'size': 'unknown' }, 'streams': [] }
            
            if self.basename.lower().endswith('.webm'):
                self.metadata['content_type'] = 'video/webm'
            elif self.basename.lower().endswith('.mp4'):
                self.metadata['content_type'] = 'video/mp4'
            elif self.basename.lower().endswith('.ogg'):
                self.metadata['content_type'] = 'video/ogg'

            if self.metadata.get('tags') and self.metadata['tags'].get('creation_time'):
                t = self.metadata['tags'].get('creation_time').split('.',1)[0]
                self.sort_key = t.replace('T', ' ')+" UTC"

            data = {
                'mtime': self.mtime,
                'size': self.size,
                'sort_key': self.sort_key,
                'metadata': self.metadata
            }
            updater.set_data(fullpath, data)

    def generate_thumbnail(self, dest_dir: str):
        thumbnail_file = f"{dest_dir}/thumb/{self.thumbname}"
        cmd = f'ffmpeg -i "{self.path}" -vcodec mjpeg -vframes 1 -an -f rawvideo -s 100x100 -y "{thumbnail_file}"'
        self.myfork(cmd)

    def generate_item(self, dest_dir: str):
        outfile = f"{dest_dir}/{self.basename}"
        # (mov|avi|flv|mp4|m4v|mpeg|mpg|webm|ogv)
        if self.basename.lower().endswith('.webm'):
            cmd = f'ffmpeg -i "{self.path}" -vcodec libvpx -acodec libvorbis -qmax 25 -y "{outfile}"'
        elif self.basename.lower().endswith('.mp4'):
            cmd = f'ffmpeg -i "{self.path}" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -movflags +faststart -vf scale=-2:720,format=yuv420p -y "{outfile}"'
        elif self.basename.lower().endswith('.ogv'):
            cmd = f'ffmpeg -i "{self.path}" -c:v libx264 -preset veryslow -crf 22 -c:a aac -b:a 128k -strict -2 -y "{outfile}"'
        self.myfork(cmd)

class Note(FileItem):
    def __init__(self, fullpath: str, relpath: str, updater: object):
        FileItem.__init__(self, fullpath, relpath, updater)
        self.type = 'note'
        self.thumbname = "res/note.png"
        thumbfile = f"{updater.dest_dir}/{relpath}/thumb/{self.thumbname}".replace('//', '/')
        if not exists(thumbfile):
            self.changed = True
        if self.changed:
            with os.popen(f"file {self.path}") as fh:
                self.metadata['magic'] = fh.read().split(': ')[1]
            self.metadata['stat'] = os.stat(self.path)
            data = {
                'mtime': self.mtime,
                'size': self.size,
                'sort_key': self.sort_key,
                'metadata': self.metadata
            }
            updater.set_data(fullpath, data)

    def generate_thumbnail(self, dest_dir: str):
        pass

    def generate_item(self, dest_dir: str):
        outfile = f"{dest_dir}/{self.basename}"
        try:
            os.link(self.path, outfile)
        except Exception:
            copyfile(self.path, outfile)
