from __future__ import print_function

from gearbox.command import TemplateCommand

class MakePackageCommand(TemplateCommand):
    def get_description(self):
        return 'Creates a basic python package'

    def get_parser(self, prog_name):
        parser = super(MakePackageCommand, self).get_parser(prog_name)

        parser.add_argument("name")

        return parser

    def take_action(self, opts):
        opts.project = opts.name
        opts.package = opts.name
        opts.author = 'Unknown'
        opts.author_email = None
        opts.url = None
        opts.license_name = None
        opts.version = '0.0.1'
        opts.description = None
        opts.long_description = None
        opts.keywords = None
        opts.zip_safe = False

        self.run_template(opts.name, opts)