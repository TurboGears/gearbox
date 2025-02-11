# -*- coding: utf-8 -*-
"""Discover and lookup command plugins.

This comes from OpenStack cliff.
"""

import importlib.metadata
import logging

LOG = logging.getLogger(__name__)


class EntryPointWrapper(object):
    """Wrap up a command class already imported to make it look like a plugin."""

    def __init__(self, name, command_class):
        self.name = name
        self.command_class = command_class

    def load(self, require=False):
        return self.command_class


class CommandManager(object):
    """Discovers commands and handles lookup based on argv data.

    :param namespace: String containing the setuptools entrypoint namespace
                      for the plugins to be loaded. For example,
                      ``'cliff.formatter.list'``.
    :param convert_underscores: Whether cliff should convert underscores to
                                spaces in entry_point commands.
    """

    def __init__(self, namespace, convert_underscores=True):
        self.commands = {}
        self.namespace = namespace
        self.convert_underscores = convert_underscores
        self._load_commands()

    def _load_commands(self):
        # NOTE(jamielennox): kept for compatability.
        self.load_commands(self.namespace)

    def load_commands(self, namespace):
        """Load all the commands from an entrypoint"""
        entry_points = importlib.metadata.entry_points()
        if hasattr(entry_points, "select"):
            entry_points = entry_points.select(group=namespace)
        else:
            entry_points = entry_points.get(namespace, [])
        for ep in entry_points:
            LOG.debug("found command %r", ep.name)
            cmd_name = (
                ep.name.replace("_", " ") if self.convert_underscores else ep.name
            )
            self.commands[cmd_name] = ep
        return

    def __iter__(self):
        return iter(self.commands.items())

    def add_command(self, name, command_class):
        self.commands[name] = EntryPointWrapper(name, command_class)

    def find_command(self, argv):
        """Given an argument list, find a command and
        return the processor and any remaining arguments.
        """
        search_args = argv[:]
        name = ""
        while search_args:
            if search_args[0].startswith("-"):
                name = "%s %s" % (name, search_args[0])
                raise ValueError("Invalid command %r" % name)
            next_val = search_args.pop(0)
            name = "%s %s" % (name, next_val) if name else next_val
            if name in self.commands:
                cmd_ep = self.commands[name]
                cmd_factory = cmd_ep.load()
                return (cmd_factory, name, search_args)
        else:
            raise ValueError("Unknown command %r" % next(iter(argv), ""))
