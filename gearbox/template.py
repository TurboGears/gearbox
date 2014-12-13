from tempita import Template
from .utils.copydir import copy_dir
import os


class GearBoxTemplate(object):
    def template_renderer(self, content, vars, filename=None):
        tmpl = Template(content, name=filename)
        return tmpl.substitute(vars)

    def pre(self, template_dir, output_dir, vars):
        pass

    def post(self, template_dir, output_dir, vars):
        pass

    def run(self, template_dir, output_dir, vars):
        self.pre(template_dir, output_dir, vars)
        self.write_files(template_dir, output_dir, vars)
        self.post(template_dir, output_dir, vars)

    def write_files(self, template_dir, output_dir, vars):
        if not os.path.exists(output_dir):
            print("Creating directory %s" % output_dir)
            os.makedirs(output_dir)

        copy_dir(template_dir, output_dir, vars, indent=1,
                 template_renderer=self.template_renderer)