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
        basedir = dirname(dirname(__file__))
        if exists(f"{basedir}/templates/{scheme_name}"):
            templates = {}
            for x in ['folder', 'image', 'video', 'note']:
                filename = f"{basedir}/templates/{scheme_name}/{x}.html"
                with open(filename, 'r') as fh:
                    templates[x] = Template(fh.read())
                templates[x].mtime = mtime(filename)

            templates['res'] = f"{basedir}/templates/{scheme_name}/res"
            return templates