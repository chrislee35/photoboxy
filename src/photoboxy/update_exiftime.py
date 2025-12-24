import glob
import os
import piexif
import re
import time
import typer

from typing_extensions import Annotated
from datetime import datetime

def update_exiftime(
    source_dir: Annotated[str, typer.Argument(help="The path to the top directory of your images that you want to add time exif to.")],
    timestamp: Annotated[str, typer.Argument(help="Timestamp in '%Y:%m:%d %H:%M:%S' format")],
    mtime_update: Annotated[bool, typer.Option(help="Update the modified time on the file")] = False,
    force_update: Annotated[bool, typer.Option(help="Update existing time in Exif even if it already exists")] = False,
    noop: Annotated[bool, typer.Option(help="Don't change anything, just print what would have been done.")] = False,
):
    for source in glob.glob(source_dir+"/*"):
        if os.path.isdir(source): continue
        if source.lower().split('.')[-1] not in ("jpg", "jpeg"): continue
        try:
            exif_dict = piexif.load(source, key_is_name=True)
        except Exception as e:
            print(f"{source} exif parsing error: {e}")
            continue
        if 'Exif' in exif_dict and 'DateTimeOriginal' in exif_dict['Exif'] and not force_update:
            continue
        exif_dict['Exif']['DateTimeOriginal'] = timestamp
        exif_bytes = piexif.dump(exif_dict)
        if noop:
            print(f"{source} DateTimeOriginal {timestamp}")
        else:
            piexif.insert(exif_bytes, source)
        if mtime_update:
            access_time = int(time.time())
            dt = datetime.strptime(timestamp, '%Y:%m:%d %H:%M:%S')
            modification_time = int(dt.timestamp())
            if noop:
                print(f"{source} mtime {modification_time}")
            else:
                os.utime(source, (access_time, modification_time))

def update_exiftime_by_foldernames(
    source_dir: Annotated[str, typer.Argument(help="The path to the top directory of your images that you want to add time exif to.")],
    time_format: Annotated[str, typer.Option(help="time format in strftime format, e.g., %Y%m%d")] = "%Y%m%d",
    mtime_update: Annotated[bool, typer.Option(help="Update the modified time on the file")] = True,
    force_update: Annotated[bool, typer.Option(help="Update existing time in Exif even if it already exists")] = False,
    noop: Annotated[bool, typer.Option(help="Don't change anything, just print what would have been done.")] = False,
):
    for path, directories, files in os.walk(source_dir):
        if '-' not in path: continue
        if '.jalbum' in path: continue
        dtstr = None
        for part in path.split('/')[::-1]:
            d = part.split('-')[0].strip()
            try:
                dt = datetime.strptime(d, time_format)
                dtstr = dt.strftime('%Y:%m:%d 12:00:00')
                break
            except Exception as e:
                pass
        if dtstr:
            update_exiftime(path, timestamp = dtstr, mtime_update = mtime_update, force_update = force_update, noop = noop)

def update_exiftime_using_filenames( source_dir ):
    for source in glob.glob(source_dir+"/*"):
        if os.path.isdir(source): continue
        if source.lower().split('.')[-1] not in ("jpg", "jpeg"): continue
        if source.endswith('_n.jpg') or source.endswith('_o.jpg'): continue
        if 'FB_IMG_' in source: continue
        try:
            exif_dict = piexif.load(source)
        except Exception as e:
            continue
        if 'Exif' in exif_dict and piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
            continue
        filename = os.path.basename(source)
        dates = re.findall(r'(20\d{6})', filename)
        if dates:
            ts = dates[-1]
            timestamp = f"{ts[0:4]}:{ts[4:6]}:{ts[6:8]} 12:00:00"
            exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = timestamp
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, source)
            print(source, timestamp)

def count_exif_folder(
    source_dir: Annotated[str, typer.Argument(help="The path to the top directory of your images that you want to add time exif to.")],
        
) -> None:
    metrics = {
        'total': 0,
        'errors': 0,
        'has_timestamp': 0,
        'no_timestamp': 0
    }
    for source in glob.glob(source_dir+"/*"):
        if os.path.isdir(source): continue
        if source.lower().split('.')[-1] not in ("jpg", "jpeg"): continue
        metrics['total'] += 1
        try:
            exif_dict = piexif.load(source)
        except Exception as e:
            metrics['errors'] += 1
            continue
        if 'Exif' in exif_dict and piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
            metrics['has_timestamp'] += 1
        else:
            metrics['no_timestamp'] += 1
    if metrics['no_timestamp'] > 0:
        dates = re.findall(r'(\d{8})', source_dir)
        if dates:
            print(f"{source_dir} {metrics['total']} {metrics['errors']} {metrics['has_timestamp']} {metrics['no_timestamp']}")
            ts = dates[-1]
            timestamp = f"{ts[0:4]}:{ts[4:6]}:{ts[6:8]} 12:00:00"
            ans = None # input(f"Attempt to update the timestamps with {timestamp}? [Y/n] ")
            if not ans: ans = 'Y'
            if ans.upper().startswith('Y'):
                update_exiftime(source_dir, timestamp)
        else:
            update_exiftime_using_filenames(source_dir)

def count_exif(
    source_dir: Annotated[str, typer.Argument(help="The path to the top directory of your images that you want to add time exif to.")],        
):
    for path, directories, files in os.walk(source_dir):
        if '.jalbum' in path: continue
        count_exif_folder(path)
    
if __name__ == "__main__":
    app = typer.Typer()
    app.command()(count_exif)
    app()