from __future__ import print_function

import sys, os, pkg_resources
from cliff.app import App
from cliff.commandmanager import CommandManager
from gearbox.utils.plugins import find_egg_info_dir

class GearBox(App):
    def __init__(self):
        super(GearBox, self).__init__(description="TurboGears2 Gearbox toolset", 
                                      version='2.3',
                                      command_manager=CommandManager('gearbox.commands'))

        try:
            self._load_commands_for_current_dir()
        except pkg_resources.DistributionNotFound as e:
            print('Failed to load project commands, %s' % e, file=sys.stderr)

    def _load_commands_for_current_dir(self):
        egg_info_dir = find_egg_info_dir(os.getcwd())
        if egg_info_dir:
            package_name = os.path.splitext(os.path.basename(egg_info_dir))[0]

            try:
                pkg_resources.require(package_name)
            except pkg_resources.DistributionNotFound as e:
                msg = '%sNot Found%s: %s (did you run python setup.py develop?)'
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

