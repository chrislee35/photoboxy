import os
from os.path import exists, dirname
from jinja2 import Template
from dataclasses import dataclass

@dataclass
class PhotoboxTemplate:
    folder: Template
    image: Template
    video: Template
    note: Template
    shuffle: Template
    faces: Template
    faces_index: Template
    calendar: Template
    res: str

    def render(self, template_type: str, **kwargs: str | None) -> str | None:
        if hasattr(self, template_type) and template_type != 'res':
            template: Template = getattr(self, template_type)  # pyright: ignore[reportAny]
            return template.render(**kwargs)
        return None


@dataclass
class ServerTemplate:
    home: Template
    face: Template
    page: Template
    res: str

def mtime(filename: str) -> float:
    return os.stat(path=filename).st_mtime

class TemplateManager:
    @staticmethod
    def load_template(filename: str) -> Template:
        with open(file=filename, mode='r') as fh:
            template: Template = Template(source=fh.read())  # pyright: ignore[reportAny]
            template.mtime = mtime(filename)  # pyright: ignore[reportAttributeAccessIssue]
            return template

    @staticmethod
    def get_templates(scheme_name: str) -> PhotoboxTemplate | None:
        basedir: str = dirname(p=__file__)
        if exists(path=f"{basedir}/templates/{scheme_name}"):
            templates: PhotoboxTemplate = PhotoboxTemplate(
                folder=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/folder.html"),
                image=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/image.html"),
                video=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/video.html"),
                note=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/note.html"),
                shuffle=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/shuffle.html"),
                faces=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/faces.html"),
                faces_index=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/faces_index.html"),
                calendar=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/calendar.html"),
                res=f"{basedir}/templates/{scheme_name}/res"
            )
            return templates
        return None
        
    @staticmethod
    def get_server_templates(scheme_name: str) -> ServerTemplate | None:
        basedir: str = dirname(p=__file__)
        if exists(path=f"{basedir}/templates/{scheme_name}"):
            templates: ServerTemplate = ServerTemplate(
                home=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/server_home.html"),
                face=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/server_face.html"),
                page=TemplateManager.load_template(filename=f"{basedir}/templates/{scheme_name}/server_page.html"),
                res=f"{basedir}/templates/{scheme_name}/res"
            )
            return templates
        return None