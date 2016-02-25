# -*- coding: utf-8 -*-

import argparse
import sys
import traceback

from ..command import Command


class HelpAction(argparse.Action):
    """Provide a custom action so the -h and --help options
    to the main app will print a list of the commands.
    The commands are determined by checking the CommandManager
    instance, passed in as the "default" value for the action.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        app = self.default
        parser.print_help(sys.stdout)
        print('\nCommands:')
        command_manager = app.command_manager
        for name, ep in sorted(command_manager):
            try:
                factory = ep.load()
            except Exception as err:
                print('Could not load %r' % ep)
                if namespace.debug:
                    traceback.print_exc(file=sys.stdout)
                continue
            try:
                cmd = factory(app, None)
                if cmd.deprecated:
                    continue
            except Exception as err:
                print('Could not instantiate %r: %s\n' % (ep, err))
                if namespace.debug:
                    traceback.print_exc(file=sys.stdout)
                continue
            one_liner = cmd.get_description().split('\n')[0]
            print('  %-13s  %s' % (name, one_liner))
        sys.exit(0)


class HelpCommand(Command):
    """print detailed help for another command"""

    def get_parser(self, prog_name):
        parser = super(HelpCommand, self).get_parser(prog_name)
        parser.add_argument('cmd',
                            nargs='*',
                            help='name of the command',
                            )
        return parser

    def take_action(self, parsed_args):
        if not parsed_args.cmd:
            action = HelpAction(None, None, default=self.app)
            action(self.app.parser, self.app.parser, None, None)
            return 1

        try:
            the_cmd = self.app.command_manager.find_command(
                parsed_args.cmd,
            )
            cmd_factory, cmd_name, search_args = the_cmd
        except ValueError:
            # Did not find an exact match
            cmd = parsed_args.cmd[0]
            fuzzy_matches = [k[0] for k in self.app.command_manager
                             if k[0].startswith(cmd)
                             ]
            if not fuzzy_matches:
                raise
            print('Command "%s" matches:' % cmd)
            for fm in sorted(fuzzy_matches):
                print('  %s' % fm)
            return

        self.app_args.cmd = search_args
        cmd = cmd_factory(self.app, self.app_args)
        full_name = ' '.join([self.app.NAME, cmd_name])
        cmd_parser = cmd.get_parser(full_name)
        cmd_parser.print_help(sys.stdout)
        return 0