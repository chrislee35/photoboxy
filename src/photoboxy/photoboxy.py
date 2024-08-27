# -*- coding: utf-8 -*-
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


#from multiprocessing.pool import Pool, AsyncResult
#from multiprocessing import Process

VERSION = "0.0.1"
debug = True

from .updater import Updater
import typer
from typing_extensions import Annotated
import os

def generate_album(
        source_dir: Annotated[str, typer.Argument(help="The path to the top directory of your images that you want to convert into a photo album.")],
        dest_dir: Annotated[str, typer.Option(help="The output directory to place the generated album into.")] = "",
        template: Annotated[str, typer.Option(help="The name of the template to use.")] = "boring"
):
    if not os.path.exists(dest_dir):
        resp = input(f"Destination directory, {dest_dir}, does not exist.  Shall I create it? [Y/n]") 
        if resp is None or len(resp) == 0 or resp.lower().startswith('y'):
            os.makedirs(dest_dir)
        else:
            exit()
    u = Updater(source_dir, dest_dir)
    u.enumerate()
    u.generate(dest_dir, template_name=template)
    u.print_stats()
