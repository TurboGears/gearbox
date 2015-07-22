from __future__ import print_function

import sys, os, pkg_resources, logging, warnings
from cliff.app import App
from cliff.commandmanager import CommandManager
from gearbox.utils.plugins import find_egg_info_dir


class GearBox(App):
    LOG_DATE_FORMAT = '%H:%M:%S'
    LOG_GEARBOX_FORMAT = '%(asctime)s,%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s'

    def __init__(self):
        super(GearBox, self).__init__(description="TurboGears2 Gearbox toolset", 
                                      version='2.3',
                                      command_manager=CommandManager('gearbox.commands'))

        self.parser.add_argument(
            '--relative',
            default=False,
            action='store_true',
            dest='relative_plugins',
            help='Load plugins and applications also from current path.',
        )

    def initialize_app(self, args):
        if self.options.relative_plugins:
            curdir = os.getcwd()
            sys.path.insert(0, curdir)
            pkg_resources.working_set.add_entry(curdir)


        try:
            self._load_commands_for_current_dir()
        except pkg_resources.DistributionNotFound as e:
            try:
                error_msg = str(e)
            except:
                error_msg = 'Unknown Error'

            print('Failed to load project commands with error "%s", have you installed your project?' % error_msg, file=sys.stderr)

    def configure_logging(self):
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
        console = logging.StreamHandler(self.stderr)
        console_level = {0: logging.WARNING,
                         1: logging.INFO,
                         2: logging.DEBUG,
                         }.get(self.options.verbose_level, logging.DEBUG)
        console.setLevel(console_level)
        formatter = logging.Formatter(self.LOG_GEARBOX_FORMAT, datefmt=self.LOG_DATE_FORMAT)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

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


def main():
    args = sys.argv[1:]
    gearbox = GearBox()
    return gearbox.run(args)

