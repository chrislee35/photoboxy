from jinja2 import Template
import os
# function aliases
exists = os.path.exists
basename = os.path.basename
dirname = os.path.dirname

def mtime(filename):
    return os.stat(filename).st_mtime

class TemplateManager:
    @staticmethod
    def get_templates(scheme_name: str):
        basedir = dirname(__file__)
        if exists(f"{basedir}/templates/{scheme_name}"):
            templates = {}
            for x in ['folder', 'image', 'video', 'note', 'shuffle', 'faces', 'faces_index']:
                filename = f"{basedir}/templates/{scheme_name}/{x}.html"
                with open(filename, 'r') as fh:
                    templates[x] = Template(fh.read())
                templates[x].mtime = mtime(filename)

            templates['res'] = f"{basedir}/templates/{scheme_name}/res"
            return templates
        
    @staticmethod
    def get_server_templates(scheme_name: str):
        basedir = dirname(__file__)
        if exists(f"{basedir}/templates/{scheme_name}"):
            templates = {}
            for x in ['server_home', 'server_face', 'server_page']:
                filename = f"{basedir}/templates/{scheme_name}/{x}.html"
                with open(filename, 'r') as fh:
                    templates[x] = Template(fh.read())
                templates[x].mtime = mtime(filename)

            templates['res'] = f"{basedir}/templates/{scheme_name}/res"
            return templates
    