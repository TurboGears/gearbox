from __future__ import print_function

import os
import fnmatch
import re
from argparse import RawDescriptionHelpFormatter
from gearbox.command import Command


class PatchCommand(Command):
    def get_description(self):
        return r'''Patches files by replacing, appending or deleting text.

This is meant to provide a quick and easy way to replace text and
code in your projects.

Here are a few examples, this will replace all xi:include occurrences
with py:extends in all the template files recursively:

    $ gearbox patch -R '*.html' xi:include -r py:extends

It is also possible to rely on regex and python for more complex
replacements, like updating the Copyright year in your documentation:

    $ gearbox patch -R '*.rst' -x 'Copyright(\s*)(\d+)' -e -r '"Copyright\\g<1>"+__import__("datetime").datetime.utcnow().strftime("%Y")'

Works on a line by line basis, so it is not possible to match text
across multiple lines.
'''

    def get_parser(self, prog_name):
        parser = super(PatchCommand, self).get_parser(prog_name)
        parser.formatter_class = RawDescriptionHelpFormatter

        parser.add_argument('pattern',
                            help='The glob pattern of files that should be matched')

        parser.add_argument('text',
                            help='text that should be looked up in matched files.')

        parser.add_argument('-r', '--replace',
                            dest='replacement',
                            help='Replace occurrences of text with REPLACEMENT')

        parser.add_argument('-a', '--append',
                            dest='addition',
                            help='Append ADDITION after the line with matching text.')

        parser.add_argument('-d', '--delete',
                            action='store_true',
                            help='Delete lines matching text.')

        parser.add_argument('-x', '--regex',
                            dest='regex',
                            action="store_true",
                            help='Parse the text as a regular expression.')

        parser.add_argument('-R', '--recursive',
                            dest='recursive',
                            action="store_true",
                            help='Look for files matching pattern in subfolders too.')

        parser.add_argument('-e', '--eval',
                            dest='eval',
                            action='store_true',
                            help='Eval the replacement as Python code before applying it.')

        return parser

    def _walk_recursive(self):
        for root, dirnames, filenames in os.walk(os.getcwd()):
            for filename in filenames:
                yield os.path.join(root, filename)

    def _walk_flat(self):
        root = os.getcwd()
        for filename in os.listdir(root):
            yield os.path.join(root, filename)

    def _replace_regex(self, line, text, replacement):
        return re.sub(text, replacement, line)

    def _replace_plain(self, line, text, replacement):
        return line.replace(text, replacement)

    def _match_regex(self, line, text):
        return re.search(text, line) is not None

    def _match_plain(self, line, text):
        return text in line

    def take_action(self, opts):
        walk = self._walk_flat
        if opts.recursive:
            walk = self._walk_recursive

        match = self._match_plain
        if opts.regex:
            match = self._match_regex

        replace = self._replace_plain
        if opts.regex:
            replace = self._replace_regex

        matches = []
        for filepath in walk():
            if fnmatch.fnmatch(filepath, opts.pattern):
                matches.append(filepath)

        print('%s files matching' % len(matches))
        for filepath in matches:
            replacement = opts.replacement
            if opts.eval and replacement:
                replacement = str(eval(replacement, globals()))

            addition = opts.addition
            if opts.eval and addition:
                addition = str(eval(addition, globals()))

            matches = False
            lines = []
            with open(filepath) as f:
                for line in f:
                    if not match(line, opts.text):
                        lines.append(line)
                        continue

                    matches = True
                    empty_line = not line.strip()
                    if opts.replacement:
                        line = replace(line, opts.text, replacement)

                    if empty_line or line.strip() and not opts.delete:
                        lines.append(line)

                    if opts.addition:
                        lines.append(addition+'\n')

            print('%s Patching %s' % (matches and '!' or 'x', filepath))
            if matches:
                with open(filepath, 'w') as f:
                    f.writelines(lines)
