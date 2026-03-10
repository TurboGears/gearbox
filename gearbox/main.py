from __future__ import print_function

import argparse
import importlib.metadata
import inspect
import logging
import os
import re
import sys
import warnings

from .commandmanager import CommandManager
from .commands.help import HelpAction, HelpCommand
from .utils.plugins import find_local_distribution

log = logging.getLogger("gearbox")


class GearBox(object):
    NAME = os.path.splitext(os.path.basename(sys.argv[0]))[0]
    LOG_DATE_FORMAT = "%H:%M:%S"
    LOG_GEARBOX_FORMAT = (
        "%(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s"
    )
    DEFAULT_VERBOSE_LEVEL = 1

    try:
        VERSION = importlib.metadata.version("gearbox")
    except importlib.metadata.PackageNotFoundError:
        VERSION = "unknown"

    def __init__(self):
        self.command_manager = CommandManager("gearbox.commands")
        self.command_manager.add_command("help", HelpCommand)
        self.parser = argparse.ArgumentParser(
            description="TurboGears2 Gearbox toolset", add_help=False
        )

        parser = self.parser
        parser.add_argument(
            "--version",
            action="version",
            version="%(prog)s {0}".format(self.VERSION),
        )

        verbose_group = parser.add_mutually_exclusive_group()
        verbose_group.add_argument(
            "-v",
            "--verbose",
            action="count",
            dest="verbose_level",
            default=self.DEFAULT_VERBOSE_LEVEL,
            help="Increase verbosity of output. Can be repeated.",
        )
        verbose_group.add_argument(
            "-q",
            "--quiet",
            action="store_const",
            dest="verbose_level",
            const=0,
            help="Suppress output except warnings and errors.",
        )

        parser.add_argument(
            "--log-file",
            action="store",
            default=None,
            help="Specify a file to log output. Disabled by default.",
        )

        parser.add_argument(
            "-h",
            "--help",
            action=HelpAction,
            nargs=0,
            default=self,  # tricky
            help="Show this help message and exit.",
        )

        parser.add_argument(
            "--debug",
            default=False,
            action="store_true",
            help="Show tracebacks on errors.",
        )

        parser.add_argument(
            "--relative",
            default=False,
            action="store_true",
            dest="relative_plugins",
            help="Load plugins and applications also from current path.",
        )

    def _configure_logging(self):
        if self.options.debug:
            warnings.simplefilter("default")
            try:
                logging.captureWarnings(True)
            except AttributeError:
                pass

        root_logger = logging.getLogger("")
        root_logger.setLevel(logging.INFO)

        # Set up logging to a file
        if self.options.log_file:
            file_handler = logging.FileHandler(filename=self.options.log_file)
            formatter = logging.Formatter(
                self.LOG_GEARBOX_FORMAT, datefmt=self.LOG_DATE_FORMAT
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

        # Always send higher-level messages to the console via stderr
        console = logging.StreamHandler(sys.stderr)
        console_level = {
            0: logging.WARNING,
            1: logging.INFO,
            2: logging.DEBUG,
        }.get(self.options.verbose_level, logging.DEBUG)
        console.setLevel(console_level)
        formatter = logging.Formatter(
            self.LOG_GEARBOX_FORMAT, datefmt=self.LOG_DATE_FORMAT
        )
        console.setFormatter(formatter)
        root_logger.addHandler(console)

    def run(self, argv):
        """Application entry point"""
        if not argv:
            # Print help when started without a subcommand.
            argv = ["--help"]

        try:
            self.options, remainder = self.parser.parse_known_args(argv)
            self._configure_logging()

            if self.options.relative_plugins:
                curdir = os.getcwd()
                sys.path.insert(0, curdir)

            self._load_commands_for_current_dir()

        except Exception as err:
            if hasattr(self, "options"):
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
        if (
            "cmd_name" in self._getargspec(cmd_factory)[0]
        ):  # Check to see if 'cmd_name' is in cmd_factory's args
            kwargs["cmd_name"] = cmd_name
        cmd = cmd_factory(self, self.options, **kwargs)

        try:
            full_name = " ".join([self.NAME, cmd_name])
            cmd_parser = cmd.get_parser(full_name)
            parsed_args = cmd_parser.parse_args(sub_argv)
            return cmd.run(parsed_args)
        except Exception as err:
            log.exception(err)
            return 4

    def _load_commands_for_current_dir(self):
        dist, search_path = find_local_distribution(os.getcwd(), "gearbox.plugins")
        if dist is None:
            return

        for ep in dist.entry_points:
            if ep.group == "gearbox.plugins":
                self.load_commands_for_package(ep.module, search_paths=[search_path])

    def load_commands_for_package(self, package_name, search_paths=None):
        candidates = [package_name]
        top_level_package = package_name.split(".", 1)[0]
        for candidate in importlib.metadata.packages_distributions().get(
            top_level_package, []
        ):
            if candidate not in candidates:
                candidates.append(candidate)

        local_distributions = []
        if search_paths:
            for path in search_paths:
                if not path:
                    continue
                local_distributions.extend(importlib.metadata.distributions(path=[path]))

        normalized_candidates = set(
            self._normalize_dist_name(name) for name in candidates
        )
        local_candidate_distributions = []

        for dist in local_distributions:
            matched = False
            dist_name = dist.metadata.get("Name")
            if (
                dist_name
                and self._normalize_dist_name(dist_name) in normalized_candidates
            ):
                candidate_name = dist_name
                if candidate_name not in candidates:
                    candidates.append(candidate_name)
                matched = True

            top_level_names = dist.read_text("top_level.txt")
            if top_level_names:
                for top_level_name in top_level_names.splitlines():
                    if top_level_name.strip() == top_level_package:
                        candidate_name = dist.metadata.get("Name")
                        if candidate_name and candidate_name not in candidates:
                            candidates.append(candidate_name)
                        matched = True
                        break
            if matched:
                local_candidate_distributions.append(dist)

        found_distribution = False
        for dist in local_candidate_distributions:
            found_distribution = True
            loaded_commands = False
            for ep in dist.entry_points:
                if ep.group == "gearbox.project_commands":
                    self.command_manager.commands[ep.name.replace("_", " ")] = ep
                    loaded_commands = True
            if loaded_commands:
                return

        for candidate in candidates:
            if any(
                self._normalize_dist_name(dist.metadata.get("Name", ""))
                == self._normalize_dist_name(candidate)
                for dist in local_candidate_distributions
            ):
                continue

            try:
                dist = importlib.metadata.distribution(candidate)
            except importlib.metadata.PackageNotFoundError:
                continue
            found_distribution = True
            loaded_commands = False
            for ep in dist.entry_points:
                if ep.group == "gearbox.project_commands":
                    self.command_manager.commands[ep.name.replace("_", " ")] = ep
                    loaded_commands = True
            if loaded_commands:
                return

        if not found_distribution:
            log.error(
                "Failed to load project commands with error "
                "``%s``, have you installed your project?" % package_name
            )

    @staticmethod
    def _normalize_dist_name(name):
        return re.sub(r"[-_.]+", "-", name).lower()

    def _getargspec(self, func):
        if not hasattr(inspect, "signature"):
            return inspect.getargspec(func.__init__)
        else:  # pragma: no cover
            sig = inspect.signature(func)
            args = [
                p.name
                for p in sig.parameters.values()
                if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
            ]
            varargs = [
                p.name
                for p in sig.parameters.values()
                if p.kind == inspect.Parameter.VAR_POSITIONAL
            ]
            varargs = varargs[0] if varargs else None
            varkw = [
                p.name
                for p in sig.parameters.values()
                if p.kind == inspect.Parameter.VAR_KEYWORD
            ]
            varkw = varkw[0] if varkw else None
            defaults = (
                tuple(
                    (
                        p.default
                        for p in sig.parameters.values()
                        if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
                        and p.default is not p.empty
                    )
                )
                or None
            )
            return args, varargs, varkw, defaults


def main():
    args = sys.argv[1:]
    gearbox = GearBox()
    return gearbox.run(args)
