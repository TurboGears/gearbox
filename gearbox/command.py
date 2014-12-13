import argparse
import os, sys

from cliff.command import Command as CliffCommand

from .template import GearBoxTemplate


class Command(CliffCommand):
    def get_parser(self, prog_name):
        parser = argparse.ArgumentParser(description=self.get_description(),
                                         prog=prog_name,
                                         add_help=False)
        return parser


class TemplateCommand(Command):
    template = GearBoxTemplate()

    def get_template_path(self):
        module = sys.modules[self.__class__.__module__]
        module_path = module.__file__
        return os.path.join(os.path.abspath(os.path.dirname(module_path)),  'template')

    def run_template(self, output_dir, opts):
        self.template.run(self.get_template_path(), output_dir, vars(opts))


