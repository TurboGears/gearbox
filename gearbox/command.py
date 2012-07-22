import os, sys

from cliff.command import Command

from .template import GearBoxTemplate

class TemplateCommand(Command):
    template = GearBoxTemplate()

    def get_template_path(self):
        module = sys.modules[self.__module__]
        module_path = module.__file__
        return os.path.join(os.path.abspath(os.path.dirname(module_path)),  'template')

    def run_template(self, output_dir, opts):
        self.template.run(self.get_template_path(), output_dir, vars(opts))


