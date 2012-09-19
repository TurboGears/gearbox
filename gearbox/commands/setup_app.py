from __future__ import print_function

import os

from cliff.command import Command
from paste.deploy import appconfig

class SetupAppCommand(Command):
    def get_description(self):
        return "Setup an application, given a config file"

    def get_parser(self, prog_name):
        parser = super(SetupAppCommand, self).get_parser(prog_name)

        parser.add_argument('--name',
            action='store',
            dest='section_name',
            default=None,
            help='The name of the section to set up (default: app:main)')

        parser.add_argument('args', nargs='*', default=['development.ini'])

        return parser

    def take_action(self, opts):
        config_spec = opts.args[0]
        section = opts.section_name
        if section is None:
            if '#' in config_spec:
                config_spec, section = config_spec.split('#', 1)
            else:
                section = 'main'
        if not ':' in section:
            plain_section = section
            section = 'app:'+section
        else:
            plain_section = section.split(':', 1)[0]
        if not config_spec.startswith('config:'):
            config_spec = 'config:' + config_spec
        if plain_section != 'main':
            config_spec += '#' + plain_section
        config_file = config_spec[len('config:'):].split('#', 1)[0]
        config_file = os.path.join(os.getcwd(), config_file)
        conf = appconfig(config_spec, relative_to=os.getcwd())
        ep_name = conf.context.entry_point_name
        ep_group = conf.context.protocol
        dist = conf.context.distribution
        if dist is None:
            raise RuntimeError("The section %r is not the application (probably a filter).  You should add #section_name, where section_name is the section that configures your application" % plain_section)

        self._setup_config(dist, config_file, section, {}, verbosity=self.app.options.verbose_level)

    def _setup_config(self, dist, filename, section, vars, verbosity):
        """
        Called to setup an application, given its configuration
        file/directory.

        The default implementation calls
        ``package.websetup.setup_config(command, filename, section,
        vars)`` or ``package.websetup.setup_app(command, config,
        vars)``

        With ``setup_app`` the ``config`` object is a dictionary with
        the extra attributes ``global_conf``, ``local_conf`` and
        ``filename``
        """
        modules = [line.strip() for line in dist.get_metadata_lines('top_level.txt')
                    if line.strip() and not line.strip().startswith('#')]

        if not modules:
            print('No modules are listed in top_level.txt')
            print('Try running python setup.py egg_info to regenerate that file')

        for mod_name in modules:
            mod_name = mod_name + '.websetup'
            try:
                mod = self._import_module(mod_name)
            except ImportError as e:
                print(e)
                desc = getattr(e, 'args', ['No module named websetup'])[0]
                if not desc.startswith('No module named websetup'):
                    raise
                mod = None

            if mod is None:
                continue

            if hasattr(mod, 'setup_app'):
                if verbosity:
                    print('Running setup_app() from %s' % mod_name)
                self._call_setup_app(mod.setup_app, filename, section, vars)
            elif hasattr(mod, 'setup_config'):
                if verbosity:
                    print('Running setup_config() from %s' % mod_name)
                mod.setup_config(None, filename, section, vars)
            else:
                print('No setup_app() or setup_config() function in %s (%s)' % (mod.__name__, mod.__file__))

    def _call_setup_app(self, func, filename, section, vars):
        filename = os.path.abspath(filename)
        if ':' in section:
            section = section.split(':', 1)[1]
        conf = 'config:%s#%s' % (filename, section)
        conf = appconfig(conf)
        conf.filename = filename
        func(None, conf, vars)

    def _import_module(self, s):
        """
        Import a module.
        """
        mod = __import__(s)
        parts = s.split('.')
        for part in parts[1:]:
            mod = getattr(mod, part)
        return mod
