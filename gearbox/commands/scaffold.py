from __future__ import print_function

import os
from argparse import RawDescriptionHelpFormatter
from gearbox.command import Command
from gearbox.template import GearBoxTemplate
from gearbox.utils.plugins import find_egg_info_dir


class ScaffoldCommand(Command):
    def get_description(self):
        return '''Creates a new file from a scaffold template

Scaffold templates are recursively looked up inside the current path,
for example TurboGears2 projects can easily create new models, controllers
and template using something like:

    $ gearbox scaffold model controller template something

which will create a SomethingModel, SomethingController and something.html
using model/model.py.template, controllers/controller.py.template and
templates/template.html.template scaffolds of the current project.
'''

    def get_parser(self, prog_name):
        parser = super(ScaffoldCommand, self).get_parser(prog_name)

        parser.formatter_class = RawDescriptionHelpFormatter

        parser.add_argument('scaffold_name',
                            nargs='+',
                            help='One or more scaffold templates to use')

        parser.add_argument('target',
                            help='entity for which scaffold is created')

        parser.add_argument('-l', '--lookup',
                            dest='lookup',
                            help='Path where to lookup for scaffold templates.')

        parser.add_argument('-p', '--path',
                            dest='path',
                            help='Where to place the newly created files, '
                                 'by default same directory of the template')

        parser.add_argument('-s', '--subdir',
                            dest='subdir',
                            help='Place the newly created path in a subdir, '
                                 'instead of directly placing them into the path.')

        parser.add_argument('-np', '--no-package',
                            dest='nopackage',
                            help='When using subdir option do not create python '
                                 'packages, but plain directories.')

        return parser

    def _lookup(self, template, where):
        template_filename = None
        for root, __, files in os.walk(where):
            for f in files:
                fname, fext = os.path.splitext(f)
                if fext == '.template' and os.path.splitext(fname)[0] == template:
                    template_filename = os.path.join(root, f)
                    break
        return template_filename

    def _find_toplevel_packages(self):
        egg_info_dir = find_egg_info_dir(os.getcwd())
        if egg_info_dir is None:
            print('Unable to find distribution egg-info, did you run setup.py egg_info or develop?')
            return []

        modules = os.path.join(egg_info_dir, 'top_level.txt')
        try:
            modules = open(modules).readlines()
        except:
            print('Unable to detect distribution top level packages.')
            return []

        modules = map(lambda x: x.strip().replace(os.sep, '.'), modules)
        modules = filter(lambda x: not x.startswith('test'), modules)  # Remove test suite modules
        return list(modules)

    def take_action(self, opts):
        for template in opts.scaffold_name:
            template_filename = None
            template_relpath = None
            if template.endswith('.template'):
                # Template is a path, use it as it is.
                template_filename = template
                template_relpath = '.'
            else:
                # Not a template path, look it up in subfolders
                template_filename = self._lookup(template, '.')
                if template_filename:
                    template_relpath = os.path.dirname(template_filename)

                if template_filename is None and opts.lookup:
                    template_filename = self._lookup(template, opts.lookup)
                    if template_filename:
                        template_relpath = os.path.relpath(os.path.dirname(template_filename), opts.lookup)

            if not template_filename or not os.path.exists(template_filename):
                print('Template %s Not Found!' % (template))
                continue

            print('Using %s for %s' % (template_filename, opts.target))
            template_with_ext, __ = os.path.splitext(template_filename)
            __, output_ext = os.path.splitext(template_with_ext)

            output_dir = opts.path
            if not output_dir:
                output_dir = template_relpath

            if opts.subdir:
                output_dir = os.path.join(output_dir, opts.subdir)

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                if opts.subdir:
                    package_init = os.path.join(output_dir, '__init__.py')
                    if not os.path.exists(package_init):
                        with open(package_init, 'w') as pif:
                            pif.write('# -*- coding: utf-8 -*-\n')

            output_path = os.path.join(output_dir, opts.target) + output_ext
            print('Creating %s...' % output_path)

            with open(template_filename, 'r') as tf:
                try:
                    subdir_as_package = opts.subdir.replace(os.sep, '.') if opts.subdir else ''
                    text = GearBoxTemplate().template_renderer(tf.read(), {
                        'target': opts.target,
                        'subdir': opts.subdir,
                        'subpackage': subdir_as_package,
                        'dotted_subpackage': '.' + subdir_as_package,
                        'packages': self._find_toplevel_packages()
                    })
                except NameError as e:
                    print('!! Error while processing template: %s' % e)
                    continue

                with open(output_path, 'w') as of:
                    of.write(text)


