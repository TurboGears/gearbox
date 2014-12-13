from __future__ import print_function

from gearbox.command import TemplateCommand
import re


class MakePackageCommand(TemplateCommand):
    CLEAN_PACKAGE_NAME_RE = re.compile('[^a-zA-Z0-9_]')

    def get_description(self):
        return 'Creates a basic python package'

    def get_parser(self, prog_name):
        parser = super(MakePackageCommand, self).get_parser(prog_name)

        parser.add_argument('-n', '--name', dest='project',
                            metavar='NAME', required=True,
                            help="Project Name")

        parser.add_argument('-o', '--output-dir', dest='output_dir',
                            metavar='OUTPUT_DIR',
                            help="Destination directory (by default the project name)")

        parser.add_argument('-p', '--package', dest='package',
                            metavar='PACKAGE',
                            help="Python Package Name")

        parser.add_argument('-a', '--author', dest='author',
                            metavar='AUTHOR', default='Unknown',
                            help="Name of the package author")

        parser.add_argument('-e', '--email', dest='author_email',
                            metavar='AUTHOR_EMAIL',
                            help="Email of the package author")

        parser.add_argument('-u', '--url', dest='url',
                            metavar='URL',
                            help="Project homepage")

        parser.add_argument('-l', '--license', dest='license_name',
                            metavar='LICENSE_NAME',
                            help="License used for the project")

        parser.add_argument('-d', '--description', dest='description',
                            metavar='DESCRIPTION',
                            help="Package description")

        parser.add_argument('-k', '--keywords', dest='keywords',
                            metavar='KEYWORDS',
                            help="Package keywords")

        return parser

    def take_action(self, opts):
        if opts.package is None:
            opts.package = self.CLEAN_PACKAGE_NAME_RE.sub('', opts.project.lower())

        if opts.output_dir is None:
            opts.output_dir = opts.project

        opts.zip_safe = False
        opts.version = '0.0.1'

        self.run_template(opts.output_dir, opts)