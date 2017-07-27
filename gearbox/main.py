from __future__ import print_function

import argparse
import inspect
import sys
import os
import pkg_resources
import logging
import warnings

from .utils.plugins import find_egg_info_dir
from .commands.help import HelpCommand, HelpAction
from .commandmanager import CommandManager

log = logging.getLogger('gearbox')


class GearBox(object):
    NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    LOG_DATE_FORMAT = '%H:%M:%S'
    LOG_GEARBOX_FORMAT = '%(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s'
    DEFAULT_VERBOSE_LEVEL = 1

    def __init__(self):
        self.command_manager = CommandManager('gearbox.commands')
        self.command_manager.add_command('help', HelpCommand)
        self.parser = argparse.ArgumentParser(description="TurboGears2 Gearbox toolset",
                                              add_help=False)

        parser = self.parser
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s {0}'.format(
                pkg_resources.get_distribution("gearbox").version
            ),
        )

        verbose_group = parser.add_mutually_exclusive_group()
        verbose_group.add_argument(
            '-v', '--verbose',
            action='count',
            dest='verbose_level',
            default=self.DEFAULT_VERBOSE_LEVEL,
            help='Increase verbosity of output. Can be repeated.',
        )
        verbose_group.add_argument(
            '-q', '--quiet',
            action='store_const',
            dest='verbose_level',
            const=0,
            help='Suppress output except warnings and errors.',
        )

        parser.add_argument(
            '--log-file',
            action='store',
            default=None,
            help='Specify a file to log output. Disabled by default.',
        )

        parser.add_argument(
            '-h', '--help',
            action=HelpAction,
            nargs=0,
            default=self,  # tricky
            help="Show this help message and exit.",
        )

        parser.add_argument(
            '--debug',
            default=False,
            action='store_true',
            help='Show tracebacks on errors.',
        )

        parser.add_argument(
            '--relative',
            default=False,
            action='store_true',
            dest='relative_plugins',
            help='Load plugins and applications also from current path.',
        )

    def _configure_logging(self):
        if self.options.debug:
            warnings.simplefilter('default')
            try:
                logging.captureWarnings(True)
            except AttributeError:
                pass

        root_logger = logging.getLogger('')
        root_logger.setLevel(logging.INFO)

        # Set up logging to a file
        if self.options.log_file:
            file_handler = logging.FileHandler(filename=self.options.log_file)
            formatter = logging.Formatter(self.LOG_GEARBOX_FORMAT, datefmt=self.LOG_DATE_FORMAT)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        # Always send higher-level messages to the console via stderr
        console = logging.StreamHandler(sys.stderr)
        console_level = {0: logging.WARNING,
                         1: logging.INFO,
                         2: logging.DEBUG,
                         }.get(self.options.verbose_level, logging.DEBUG)
        console.setLevel(console_level)
        formatter = logging.Formatter(self.LOG_GEARBOX_FORMAT, datefmt=self.LOG_DATE_FORMAT)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    def run(self, argv):
        """Application entry point"""
        try:
            self.options, remainder = self.parser.parse_known_args(argv)
            self._configure_logging()

            if self.options.relative_plugins:
                curdir = os.getcwd()
                sys.path.insert(0, curdir)
                pkg_resources.working_set.add_entry(curdir)


            try:
                self._load_commands_for_current_dir()
            except pkg_resources.DistributionNotFound as e:
                try:
                    error_msg = repr(e)
                except:
                    error_msg = 'Unknown Error'

                log.error('Failed to load project commands with error '
                          '``%s``, have you installed your project?' % error_msg)

        except Exception as err:
            if hasattr(self, 'options'):
                debug = self.options.debug
            else:
                debug = True

            if debug:
                log.exception(err)
            else:
                log.error(err)

            return 1

        return self._run_subcommand(remainder)

    def _run_subcommand(self, argv):
        try:
            subcommand = self.command_manager.find_command(argv)
        except ValueError as err:
            if self.options.debug:
                log.exception(err)
            else:
                log.error(err)
            return 2

        cmd_factory, cmd_name, sub_argv = subcommand
        kwargs = {}
        if 'cmd_name' in self._getargspec(cmd_factory)[0]:  # Check to see if 'cmd_name' is in cmd_factory's args
            kwargs['cmd_name'] = cmd_name
        cmd = cmd_factory(self, self.options, **kwargs)

        try:
            full_name = ' '.join([self.NAME, cmd_name])
            cmd_parser = cmd.get_parser(full_name)
            parsed_args = cmd_parser.parse_args(sub_argv)
            return cmd.run(parsed_args)
        except Exception as err:
            log.exception(err)
            return 4

    def _load_commands_for_current_dir(self):
        egg_info_dir = find_egg_info_dir(os.getcwd())
        if egg_info_dir:
            package_name = os.path.splitext(os.path.basename(egg_info_dir))[0]

            try:
                pkg_resources.require(package_name)
            except pkg_resources.DistributionNotFound as e:
                msg = '%sNot Found%s: %s (is it an installed Distribution?)'
                if str(e) != package_name:
                    raise pkg_resources.DistributionNotFound(msg % (str(e) + ': ', ' for', package_name))
                else:
                    raise pkg_resources.DistributionNotFound(msg % ('', '', package_name))

            dist = pkg_resources.get_distribution(package_name)
            for epname, ep in dist.get_entry_map('gearbox.plugins').items():
                self.load_commands_for_package(ep.module_name)

    def load_commands_for_package(self, package_name):
        dist = pkg_resources.get_distribution(package_name)
        for epname, ep in dist.get_entry_map('gearbox.project_commands').items():
            self.command_manager.commands[epname.replace('_', ' ')] = ep

    def _getargspec(self, func):
        if not hasattr(inspect, 'signature'):
            return inspect.getargspec(func.__init__)
        else:  # pragma: no cover
            sig = inspect.signature(func)
            args = [
                p.name for p in sig.parameters.values()
                if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
            ]
            varargs = [
                p.name for p in sig.parameters.values()
                if p.kind == inspect.Parameter.VAR_POSITIONAL
            ]
            varargs = varargs[0] if varargs else None
            varkw = [
                p.name for p in sig.parameters.values()
                if p.kind == inspect.Parameter.VAR_KEYWORD
            ]
            varkw = varkw[0] if varkw else None
            defaults = tuple((
                p.default for p in sig.parameters.values()
                if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD and p.default is not p.empty
            )) or None
            return args, varargs, varkw, defaults


def main():
    args = sys.argv[1:]
    gearbox = GearBox()
    return gearbox.run(args)

