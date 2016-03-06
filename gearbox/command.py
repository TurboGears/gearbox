import argparse
import inspect
import os, sys

from .template import GearBoxTemplate


class Command(object):
    deprecated = False

    def __init__(self, app, app_args, cmd_name=None):
        self.app = app
        self.app_args = app_args
        self.cmd_name = cmd_name

    def get_description(self):
        """Override to provide custom description for command."""
        return inspect.getdoc(self.__class__) or ''

    def get_parser(self, prog_name):
        """Override to add command options."""
        parser = argparse.ArgumentParser(description=self.get_description(),
                                         prog=prog_name, add_help=False)
        return parser

    def take_action(self, parsed_args):
        """Override to do something useful."""
        raise NotImplementedError

    def run(self, parsed_args):
        self.take_action(parsed_args)
        return 0


class TemplateCommand(Command):
    template = GearBoxTemplate()

    def get_template_path(self):
        module = sys.modules[self.__class__.__module__]
        module_path = module.__file__
        return os.path.join(os.path.abspath(os.path.dirname(module_path)),  'template')

    def run_template(self, output_dir, opts):
        self.template.run(self.get_template_path(), output_dir, vars(opts))


