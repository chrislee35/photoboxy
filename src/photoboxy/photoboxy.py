# -*- coding: utf-8 -*-
from .updater import Updater
import typer
from typing_extensions import Annotated
import os

def generate_album(
    source_dir: Annotated[str, typer.Argument(help="The path to the top directory of your images that you want to convert into a photo album.")],
    dest_dir: Annotated[str, typer.Option(help="The output directory to place the generated album into.")] = "",
    template: Annotated[str, typer.Option(help="The name of the template to use.")] = "boring",
    htmlonly: Annotated[bool, typer.Option(help="Set if you want to regenerate all the html.")] = False,
    skip_videos: Annotated[bool, typer.Option(help="Skip the processing of videos.")] = False,
    skip_docs: Annotated[bool, typer.Option(help="Skip the processing of documents.")] = False,
    use_pca: Annotated[bool, typer.Option(help="Use PCA before clustering")] = False,
    recluster: Annotated[bool, typer.Option(help="Ensure full reclustering")] = False
) -> None:
    if not os.path.exists(path=dest_dir):
        resp: str = input(f"Destination directory, {dest_dir}, does not exist.  Shall I create it? [Y/n]") 
        if len(resp) == 0 or resp.lower().startswith('y'):
            os.makedirs(name=dest_dir)
        else:
            exit()
    u: Updater = Updater(fullpath=source_dir, dest_dir=dest_dir)
    u.config.htmlonly = htmlonly
    u.config.skip_videos = skip_videos
    u.config.skip_docs = skip_docs
    u.config.use_pca = use_pca
    
    u.enumerate()
    recluster = False # force reclustering for testing
    if u.needs_clustering() and not htmlonly or recluster:
        u.cluster()
    u.generate(dest_dir, template_name=template)
    u.print_stats()
