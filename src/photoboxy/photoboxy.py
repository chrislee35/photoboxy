# -*- coding: utf-8 -*-
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
    if u.needs_clustering():
        u.cluster()
    else:
        u.load_cluster()
    u.generate(dest_dir, template_name=template)
    u.print_stats()
